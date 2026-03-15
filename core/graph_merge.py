"""그래프 병합(graph merge) 모듈.

여러 파일의 추출 결과를 병합하고, 동명이인을 감지·분리하는 함수를 제공한다.
"""

import time

from core.claude_client import call_claude, parse_claude_response
from core.constants import IMPORTANCE_WEIGHTS, SYMBOLIC_WEIGHTS
from core.prompts import HOMONYM_PROMPT
from core.text_utils import normalize_id


def format_node_list(nodes_map: dict) -> str:
    """노드 맵을 사람이 읽을 수 있는 목록 문자열로 변환한다."""
    type_labels = {
        "person": "인물", "organization": "단체", "event": "사건",
        "location": "장소", "concept": "개념",
    }
    lines = []
    for nid, node in sorted(nodes_map.items()):
        label = type_labels.get(node["type"], node["type"])
        lines.append(f"- [{label}] {node['name']} (ID: {nid}): {node['description']}")
    return "\n".join(lines)


def detect_homonyms(name: str, descriptions: list[str]) -> dict:
    """동일 이름의 엔티티들이 동명이인(homonym)인지 판별한다."""
    desc_text = "\n".join(f"- 문서 {i+1}: {d}" for i, d in enumerate(descriptions))
    prompt = HOMONYM_PROMPT.format(name=name, descriptions=desc_text)
    raw_response = call_claude(prompt)
    return parse_claude_response(raw_response)


def merge_results(all_results: list[dict]) -> dict:
    """여러 파일의 추출 결과를 병합하고 중복을 제거한다."""
    nodes_map: dict[str, dict] = {}
    links_map: dict[tuple, dict] = {}
    # 동명이인 감지용: 이름 → [(id, description, source_file)] 매핑
    name_occurrences: dict[str, list[dict]] = {}

    for result in all_results:
        for entity in result.get("entities", []):
            eid = normalize_id(entity.get("id", entity["name"]))
            name = entity["name"]
            desc = entity.get("description", "")

            # 동명이인 추적
            if name not in name_occurrences:
                name_occurrences[name] = []
            name_occurrences[name].append({"id": eid, "description": desc})

            if eid in nodes_map:
                existing = nodes_map[eid]
                if len(desc) > len(existing["description"]):
                    existing["description"] = desc
            else:
                nodes_map[eid] = {
                    "id": eid,
                    "name": name,
                    "type": entity.get("type", "concept"),
                    "description": desc,
                }

        for rel in result.get("relationships", []):
            source = normalize_id(rel["source"])
            target = normalize_id(rel["target"])
            relation = rel.get("type", "related_to")
            link_key = (source, target, relation)

            # description: LLM이 "왜" 이 관계를 추출했는지에 대한 추론 근거
            description = rel.get("description", "")
            # strength: LLM이 평가한 관계 강도(1~10), 없으면 5(기본)
            strength = rel.get("strength", 5)
            if link_key in links_map:
                links_map[link_key]["weight"] += 1
                # 여러 문서에서 추출된 경우 최대 strength 채택
                links_map[link_key]["strength"] = max(
                    links_map[link_key].get("strength", 5), strength
                )
                # 더 긴 description 채택
                if len(description) > len(links_map[link_key].get("description", "")):
                    links_map[link_key]["description"] = description
            else:
                links_map[link_key] = {
                    "source": source,
                    "target": target,
                    "weight": 1,
                    "strength": strength,
                    "relation": relation,
                    "description": description,
                }

    # 링크의 source/target이 노드에 존재하는지 검증
    valid_links = [
        link for link in links_map.values()
        if link["source"] in nodes_map and link["target"] in nodes_map
    ]

    # degree 자동 계산
    for node in nodes_map.values():
        node["degree"] = 0
    for link in valid_links:
        nodes_map[link["source"]]["degree"] += 1
        nodes_map[link["target"]]["degree"] += 1

    # 역사적 중요도 가중치 적용
    for node in nodes_map.values():
        weight = 0
        desc = node.get("description", "")
        name = node["name"]

        # 직책 기반 가중치
        for title, w in IMPORTANCE_WEIGHTS.items():
            if title in desc:
                weight = max(weight, w)

        # 이름 기반 상징성 가중치
        if name in SYMBOLIC_WEIGHTS:
            weight = max(weight, SYMBOLIC_WEIGHTS[name])

        node["importance_weight"] = weight
        # degree에 가중치 반영 (기본 degree + 가중치 * 3)
        node["degree"] += weight * 3

    return {
        "nodes": list(nodes_map.values()),
        "links": valid_links,
        "name_occurrences": name_occurrences,
    }


def _merge_duplicate_nodes(nodes_map: dict, links: list, canonical_id: str, duplicate_ids: list[str]):
    """중복 노드를 canonical_id로 병합하고 관련 링크를 갱신한다."""
    canonical = nodes_map[canonical_id]

    for dup_id in duplicate_ids:
        if dup_id == canonical_id or dup_id not in nodes_map:
            continue
        dup_node = nodes_map[dup_id]
        # 더 긴 description 채택
        if len(dup_node.get("description", "")) > len(canonical.get("description", "")):
            canonical["description"] = dup_node["description"]
        # degree 합산 (가중치 제외 원본 degree)
        canonical["degree"] = canonical.get("degree", 0) + dup_node.get("degree", 0)
        # importance_weight 최대값 채택
        canonical["importance_weight"] = max(
            canonical.get("importance_weight", 0),
            dup_node.get("importance_weight", 0),
        )
        del nodes_map[dup_id]

    # 링크의 source/target을 canonical_id로 갱신
    seen_links = set()
    merged_links = []
    for link in links:
        src = link["source"]
        tgt = link["target"]
        if src in duplicate_ids:
            src = canonical_id
        if tgt in duplicate_ids:
            tgt = canonical_id
        # 자기 자신 참조(self-loop) 제거
        if src == tgt:
            continue
        link_key = (src, tgt, link.get("relation", "related_to"))
        if link_key in seen_links:
            continue
        seen_links.add(link_key)
        link["source"] = src
        link["target"] = tgt
        merged_links.append(link)

    return merged_links


def resolve_homonyms(graph: dict) -> dict:
    """동명이인을 감지·분리하고, 동일 인물의 중복 노드를 병합한다."""
    name_occ = graph.pop("name_occurrences", {})
    nodes_map = {n["id"]: n for n in graph["nodes"]}

    # 서로 다른 ID로 추출된 동일 이름 감지
    for name, occurrences in name_occ.items():
        unique_ids = list({occ["id"] for occ in occurrences})
        unique_descs = list({occ["description"] for occ in occurrences if occ["description"]})

        # ID가 하나뿐이면 중복 없음
        if len(unique_ids) <= 1:
            continue

        # description이 모두 동일하면 AI 호출 없이 바로 병합
        if len(unique_descs) <= 1:
            # 노드맵에 실제 존재하는 ID만 필터
            existing_ids = [uid for uid in unique_ids if uid in nodes_map]
            if len(existing_ids) > 1:
                # 가장 긴 description을 가진 노드를 canonical로 선택
                canonical_id = max(existing_ids, key=lambda uid: len(nodes_map[uid].get("description", "")))
                dup_ids = [uid for uid in existing_ids if uid != canonical_id]
                print(f"  [자동 병합] {name}: {len(dup_ids)}개 중복 ID → {canonical_id}")
                graph["links"] = _merge_duplicate_nodes(nodes_map, graph["links"], canonical_id, existing_ids)
            continue

        # 동명이인 여부를 AI로 판별
        print(f"  [동명이인 검사] {name} ({len(unique_descs)}개 설명)")
        try:
            result = detect_homonyms(name, unique_descs)
            if result.get("is_homonym"):
                print(f"    → 동명이인 확인: {len(result.get('persons', []))}명으로 분리")
                persons = result.get("persons", [])
                for p in persons:
                    suffix = p.get("id_suffix", "")
                    new_id = normalize_id(f"{name}_{suffix}")
                    if new_id not in nodes_map:
                        nodes_map[new_id] = {
                            "id": new_id,
                            "name": f"{name} ({p.get('role', suffix)})",
                            "type": "person",
                            "description": p.get("description", ""),
                            "degree": 0,
                            "importance_weight": SYMBOLIC_WEIGHTS.get(name, 0),
                        }
            else:
                # 동일 인물 확인 → 중복 노드 병합
                existing_ids = [uid for uid in unique_ids if uid in nodes_map]
                if len(existing_ids) > 1:
                    canonical_id = max(existing_ids, key=lambda uid: len(nodes_map[uid].get("description", "")))
                    dup_ids = [uid for uid in existing_ids if uid != canonical_id]
                    print(f"    → 동일 인물 확인, 병합: {dup_ids} → {canonical_id}")
                    graph["links"] = _merge_duplicate_nodes(nodes_map, graph["links"], canonical_id, existing_ids)
                else:
                    print(f"    → 동일 인물 확인")
            time.sleep(1)
        except Exception as e:
            print(f"    → 동명이인 판별 실패: {e}")

    graph["nodes"] = list(nodes_map.values())
    return graph
