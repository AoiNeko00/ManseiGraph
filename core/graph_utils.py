"""그래프 유틸리티(graph utility) 모듈.

그래프 JSON의 로드/저장, 노드 인덱스 구축, degree 계산,
고립 노드 탐색, 관련 파일 탐색, 관계 추가 등의 함수를 제공한다.
"""

import glob
import json
import os
import re

from core.text_utils import normalize_id


def load_graph(path: str) -> dict:
    """기존 그래프 JSON을 로드한다."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_graph(graph: dict, path: str) -> None:
    """그래프를 JSON 파일로 저장한다."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)


def build_node_index(graph: dict) -> dict[str, dict]:
    """노드 리스트를 ID 기반 딕셔너리로 변환한다."""
    return {n["id"]: n for n in graph["nodes"]}


def compute_degree(graph: dict) -> None:
    """모든 노드의 degree를 링크 기반으로 재계산한다."""
    node_index = build_node_index(graph)
    for node in graph["nodes"]:
        node["degree"] = 0

    for link in graph["links"]:
        src = link["source"]
        tgt = link["target"]
        if src in node_index:
            node_index[src]["degree"] += 1
        if tgt in node_index:
            node_index[tgt]["degree"] += 1


def find_isolated_nodes(graph: dict) -> list[dict]:
    """degree=0인 고립 노드를 찾는다."""
    connected_ids = set()
    for link in graph["links"]:
        connected_ids.add(link["source"])
        connected_ids.add(link["target"])

    return [n for n in graph["nodes"] if n["id"] not in connected_ids]


def format_existing_nodes(graph: dict, exclude_id: str = "") -> str:
    """기존 노드 목록을 사람이 읽을 수 있는 문자열로 변환한다."""
    lines = []
    for node in sorted(graph["nodes"], key=lambda n: -n.get("degree", 0)):
        if node["id"] == exclude_id:
            continue
        type_label = {"person": "인물", "organization": "단체", "event": "사건",
                       "location": "장소", "concept": "개념"}.get(node["type"], node["type"])
        lines.append(f"- [{type_label}] {node['name']} (ID: {node['id']})")
    return "\n".join(lines[:80])  # 상위 80개만 (프롬프트 길이 제한)


def find_relevant_files(node_name: str, input_dir: str) -> list[str]:
    """특정 인물과 관련된 입력 파일을 찾는다.

    공백·특수문자를 제거한 정규화 이름으로도 매칭하여 누락을 방지한다.
    """
    # 공백/특수문자 제거한 정규화 이름 (예: "김 구" → "김구")
    normalized_name = re.sub(r'[\s·.\-()（）]+', '', node_name)
    relevant = []
    for filepath in sorted(glob.glob(os.path.join(input_dir, "*.txt"))):
        basename = os.path.basename(filepath)
        normalized_basename = re.sub(r'[\s·.\-()（）_]+', '', basename)
        # 파일명에 인물 이름이 포함되어 있으면 우선 탐색
        if node_name in basename or normalized_name in normalized_basename:
            relevant.insert(0, filepath)
        else:
            # 파일 내용에 인물 이름이 포함되어 있으면 추가
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    # 전체를 읽지 않고 앞부분만 확인(효율성)
                    head = f.read(5000)
                if node_name in head or normalized_name in head.replace(" ", ""):
                    relevant.append(filepath)
            except Exception:
                pass
    return relevant


def find_underlinked_important_nodes(
    graph: dict,
    min_importance: int = 4,
    min_links_threshold: int = 10,
) -> list[dict]:
    """역사적 중요도가 높지만 연결이 부족한 노드를 찾는다.

    조건: importance_weight >= min_importance이면서 실제 link 수 < min_links_threshold인 노드.
    사전 정의된 고중요도 인물 목록도 포함하여, importance_weight가
    아직 산정되지 않은 경우에도 누락 없이 탐색한다.
    """
    # 실제 링크(link) 수 계산 (degree가 아닌 raw link count)
    link_count: dict[str, int] = {}
    for link in graph["links"]:
        link_count[link["source"]] = link_count.get(link["source"], 0) + 1
        link_count[link["target"]] = link_count.get(link["target"], 0) + 1

    # 사전 정의: importance_weight 미산정이어도 반드시 확인할 인물
    KNOWN_HIGH_IMPORTANCE = {
        "김구", "이승만", "안중근", "안창호", "손병희", "홍범도", "김좌진",
        "신채호", "조소앙", "윤봉길", "이봉창", "김원봉", "여운형", "이동녕",
        "이시영", "서재필", "유관순", "이회영", "김규식", "지청천",
    }

    candidates = []
    for node in graph["nodes"]:
        if node["type"] != "person":
            continue
        actual_links = link_count.get(node["id"], 0)
        importance = node.get("importance_weight", 0)

        # 조건 1: importance >= min_importance이고 link < min_links_threshold
        # 조건 2: 사전 고중요도 목록에 있고 link < min_links_threshold
        # 괄호(반각/전각), 공백, 특수문자를 제거하고 비교
        base_name = re.split(r'[(\（]', node["name"])[0].strip()
        is_known = base_name in KNOWN_HIGH_IMPORTANCE
        if (importance >= min_importance or is_known) \
                and actual_links < min_links_threshold:
            node["_actual_links"] = actual_links
            node["_effective_importance"] = max(importance, 4 if is_known else 0)
            candidates.append(node)

    return candidates


def add_relations_to_graph(
    graph: dict,
    result: dict,
    node_index: dict,
    existing_links: set,
) -> tuple[int, int]:
    """LLM 응답에서 관계와 엔티티를 그래프에 추가한다. (new_links, new_nodes) 반환."""
    new_links = 0
    new_nodes = 0

    # 새 엔티티 등록
    for entity in result.get("new_entities", []):
        eid = normalize_id(entity.get("id", entity["name"]))
        if eid not in node_index:
            new_node = {
                "id": eid,
                "name": entity["name"],
                "type": entity.get("type", "concept"),
                "description": entity.get("description", ""),
                "degree": 0,
                "importance_weight": 0,
            }
            graph["nodes"].append(new_node)
            node_index[eid] = new_node
            new_nodes += 1

    # 새 관계 등록
    for rel in result.get("found_relations", []):
        source = normalize_id(rel["source"])
        target = normalize_id(rel["target"])
        relation = rel.get("relation", "related_to")

        # target이 노드에 없으면 target_name으로 새 노드 생성
        if target not in node_index and rel.get("target_name"):
            new_node = {
                "id": target,
                "name": rel["target_name"],
                "type": "person",
                "description": "",
                "degree": 0,
                "importance_weight": 0,
            }
            graph["nodes"].append(new_node)
            node_index[target] = new_node
            new_nodes += 1

        link_key = (source, target, relation)
        reverse_key = (target, source, relation)
        if link_key not in existing_links and reverse_key not in existing_links:
            if source in node_index and target in node_index:
                graph["links"].append({
                    "source": source,
                    "target": target,
                    "weight": 1,
                    "relation": relation,
                })
                existing_links.add(link_key)
                new_links += 1

    return new_links, new_nodes
