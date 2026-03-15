#!/usr/bin/env python3
"""의미 기반 중복 노드 탐지 및 병합(semantic deduplication) 스크립트.

3단계로 중복을 탐지한다:
  1. 이름 정규화: 공백/가운데점 제거 + 동의어 접미사 치환 후 동일하면 후보
  2. 임베딩 유사도: 같은 타입 노드 쌍의 코사인 유사도 > threshold이면 후보
  3. LLM 확인: 후보 쌍을 Claude에 질의하여 동일 엔티티인지 최종 판정

병합 시:
  - degree가 높은 쪽을 canonical로 선택
  - description은 더 긴 쪽 채택
  - 링크는 canonical로 재매핑, 중복 링크와 자기 참조 제거

Usage:
    python3 scripts/deduplicate_semantic.py                # 탐지만 (dry run)
    python3 scripts/deduplicate_semantic.py --apply         # 탐지 + 병합 적용
    python3 scripts/deduplicate_semantic.py --no-llm        # LLM 확인 없이 규칙만
    python3 scripts/deduplicate_semantic.py --apply --no-llm
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

_GRAPH_ADVANCED = BASE_DIR / "data" / "output" / "graph_advanced.json"
_GRAPH_DEFAULT = BASE_DIR / "data" / "output" / "graph.json"
GRAPH_PATH = _GRAPH_ADVANCED if _GRAPH_ADVANCED.exists() else _GRAPH_DEFAULT

# ─── 동의어 접미사(synonym suffix) 매핑 ───

SUFFIX_SYNONYMS = {
    "대첩": "전투",
    "학살": "참변",
    "만세운동": "운동",
    "봉기": "운동",
}

# 정규화 시 제거할 문자
NORMALIZE_STRIP = re.compile(r'[\s·.\-()（）_]+')


def normalize_name(name: str) -> str:
    """이름을 정규화한다. 공백/특수문자 제거 + 동의어 접미사 치환."""
    n = NORMALIZE_STRIP.sub('', name)
    for synonym, canonical in SUFFIX_SYNONYMS.items():
        if n.endswith(synonym):
            n = n[:-len(synonym)] + canonical
    return n.lower()


def find_name_duplicates(nodes: list[dict]) -> list[tuple[dict, dict]]:
    """이름 정규화 후 동일한 노드 쌍을 찾는다."""
    by_norm: dict[str, list[dict]] = defaultdict(list)
    for node in nodes:
        key = (normalize_name(node["name"]), node["type"])
        by_norm[key].append(node)

    pairs = []
    for key, group in by_norm.items():
        if len(group) < 2:
            continue
        # 모든 쌍 생성
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                pairs.append((group[i], group[j]))
    return pairs


def find_embedding_duplicates(
    nodes: list[dict],
    threshold: float = 0.88,
) -> list[tuple[dict, dict, float]]:
    """임베딩 유사도가 높은 동일 타입 노드 쌍을 찾는다."""
    from core.embedding import load_embeddings

    emb_data = load_embeddings()
    if emb_data is None:
        print("  임베딩 파일 없음 — 건너뜀")
        return []

    import numpy as np

    embeddings, node_ids = emb_data
    id_to_idx = {nid: i for i, nid in enumerate(node_ids)}
    node_map = {n["id"]: n for n in nodes}

    # 정규화
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized = embeddings / norms

    # 타입별 그룹
    type_groups: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        if node["id"] in id_to_idx:
            type_groups[node["type"]].append(node["id"])

    pairs = []
    for node_type, ids in type_groups.items():
        if len(ids) < 2:
            continue
        indices = [id_to_idx[nid] for nid in ids]
        sub_matrix = normalized[indices]
        sim_matrix = sub_matrix @ sub_matrix.T

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                sim = float(sim_matrix[i, j])
                if sim >= threshold:
                    n1 = node_map.get(ids[i])
                    n2 = node_map.get(ids[j])
                    if n1 and n2:
                        pairs.append((n1, n2, sim))

    # 유사도 내림차순 정렬
    pairs.sort(key=lambda x: -x[2])
    return pairs


def confirm_with_llm(node_a: dict, node_b: dict) -> bool:
    """LLM에 두 노드가 동일 엔티티인지 질의한다."""
    from core.claude_client import call_claude, parse_claude_response

    prompt = f"""다음 두 엔티티가 동일한 대상(사건/인물/단체/장소)인지 판단하세요.

엔티티 A:
- 이름: {node_a['name']}
- 타입: {node_a['type']}
- 설명: {node_a.get('description', '')}

엔티티 B:
- 이름: {node_b['name']}
- 타입: {node_b['type']}
- 설명: {node_b.get('description', '')}

JSON으로 답하세요:
{{"is_same": true/false, "reason": "판단 근거"}}"""

    raw = call_claude(prompt)
    try:
        result = parse_claude_response(raw)
        return result.get("is_same", False)
    except (ValueError, KeyError):
        return False


def merge_nodes(
    graph: dict,
    merge_pairs: list[tuple[str, str]],
) -> dict:
    """확정된 병합 쌍을 적용하여 그래프를 정리한다.

    Args:
        graph: 원본 그래프.
        merge_pairs: [(keep_id, remove_id), ...] 리스트.

    Returns:
        병합된 그래프.
    """
    # ID 리매핑 테이블 구축
    id_map: dict[str, str] = {}
    for keep_id, remove_id in merge_pairs:
        # 연쇄 리매핑 처리 (A→B, B→C → A→C)
        final = keep_id
        while final in id_map:
            final = id_map[final]
        id_map[remove_id] = final

    remove_ids = set(id_map.keys())
    node_map = {n["id"]: n for n in graph["nodes"]}

    # 병합 대상의 description이 더 길면 canonical에 반영
    for remove_id, keep_id in id_map.items():
        remove_node = node_map.get(remove_id)
        keep_node = node_map.get(keep_id)
        if remove_node and keep_node:
            if len(remove_node.get("description", "")) > len(keep_node.get("description", "")):
                keep_node["description"] = remove_node["description"]

    # 노드 필터
    new_nodes = [n for n in graph["nodes"] if n["id"] not in remove_ids]

    # 링크 리매핑 + 중복/자기참조 제거
    seen_links: set[tuple] = set()
    new_links = []
    for link in graph["links"]:
        src = link["source"] if isinstance(link["source"], str) else link["source"].get("id", "")
        tgt = link["target"] if isinstance(link["target"], str) else link["target"].get("id", "")

        src = id_map.get(src, src)
        tgt = id_map.get(tgt, tgt)

        if src == tgt:
            continue

        link_key = (min(src, tgt), max(src, tgt), link.get("relation", ""))
        if link_key in seen_links:
            continue
        seen_links.add(link_key)

        link["source"] = src
        link["target"] = tgt
        new_links.append(link)

    # degree 재계산
    degree_count: dict[str, int] = defaultdict(int)
    for link in new_links:
        degree_count[link["source"]] += 1
        degree_count[link["target"]] += 1
    for node in new_nodes:
        node["degree"] = degree_count.get(node["id"], 0)

    graph["nodes"] = new_nodes
    graph["links"] = new_links

    # communities 목록이 있으면 nodeCount 갱신
    if "communities" in graph:
        comm_counts: dict[str, int] = defaultdict(int)
        for n in new_nodes:
            cid = n.get("communityId", "uncategorized")
            comm_counts[cid] += 1
        for comm in graph["communities"]:
            comm["nodeCount"] = comm_counts.get(comm["id"], 0)

    return graph


def run(apply: bool = False, use_llm: bool = True) -> None:
    """의미 기반 중복 탐지를 실행한다."""
    print("=== 의미 기반 중복 탐지 시작 ===")

    from core.graph_utils import load_graph
    graph = load_graph(str(GRAPH_PATH))
    nodes = graph["nodes"]
    print(f"입력: {len(nodes)}개 노드, {len(graph['links'])}개 링크")

    # ─── 1단계: 이름 정규화 매칭 ───
    print("\n--- 1단계: 이름 정규화 매칭 ---")
    name_pairs = find_name_duplicates(nodes)
    print(f"  후보: {len(name_pairs)}쌍")
    for a, b in name_pairs:
        print(f"    {a['name']} ({a['id']}) ↔ {b['name']} ({b['id']})")

    # ─── 2단계: 임베딩 유사도 매칭 ───
    print("\n--- 2단계: 임베딩 유사도 매칭 ---")
    emb_pairs = find_embedding_duplicates(nodes, threshold=0.88)
    # 1단계에서 이미 잡힌 쌍 제외
    name_pair_ids = {
        (min(a["id"], b["id"]), max(a["id"], b["id"]))
        for a, b in name_pairs
    }
    emb_only = [
        (a, b, sim) for a, b, sim in emb_pairs
        if (min(a["id"], b["id"]), max(a["id"], b["id"])) not in name_pair_ids
    ]
    # LLM 없이 모드에서는 임베딩 후보를 건너뜀 (대부분 다른 인물이므로)
    if not use_llm:
        print(f"  (--no-llm 모드: 임베딩 후보는 LLM 확인 필요 → 건너뜀)")
        emb_only = []
    print(f"  후보 (이름 매칭 제외): {len(emb_only)}쌍")
    for a, b, sim in emb_only[:20]:
        print(f"    {a['name']} ↔ {b['name']} (sim={sim:.3f})")

    # ─── 3단계: LLM 확인 ───
    all_candidates: list[tuple[dict, dict]] = list(name_pairs)
    for a, b, sim in emb_only:
        all_candidates.append((a, b))

    if not all_candidates:
        print("\n중복 후보 없음.")
        return

    confirmed_pairs: list[tuple[str, str]] = []  # (keep_id, remove_id)

    print(f"\n--- 3단계: 확인 ({len(all_candidates)}쌍) ---")
    for a, b in all_candidates:
        if use_llm:
            print(f"  LLM 확인: {a['name']} ↔ {b['name']}...", end=" ")
            is_same = confirm_with_llm(a, b)
            print("→ 동일" if is_same else "→ 별개")
        else:
            # LLM 없이: 이름 정규화 매칭은 자동 확정, 임베딩만은 건너뜀
            is_same = (
                normalize_name(a["name"]) == normalize_name(b["name"])
                and a["type"] == b["type"]
            )
            if is_same:
                print(f"  규칙 확정: {a['name']} ↔ {b['name']}")

        if is_same:
            # degree가 높은 쪽을 keep
            if a.get("degree", 0) >= b.get("degree", 0):
                confirmed_pairs.append((a["id"], b["id"]))
            else:
                confirmed_pairs.append((b["id"], a["id"]))

    print(f"\n=== 확정된 병합 쌍: {len(confirmed_pairs)}개 ===")
    for keep, remove in confirmed_pairs:
        keep_node = next(n for n in nodes if n["id"] == keep)
        remove_node = next(n for n in nodes if n["id"] == remove)
        print(f"  {remove_node['name']} ({remove}) → {keep_node['name']} ({keep})")

    if not confirmed_pairs:
        print("병합 대상 없음.")
        return

    if not apply:
        print("\n(dry run) --apply 옵션으로 실제 병합을 수행하세요.")
        return

    # ─── 병합 적용 ───
    print("\n--- 병합 적용 ---")
    before_nodes = len(graph["nodes"])
    before_links = len(graph["links"])

    graph = merge_nodes(graph, confirmed_pairs)

    print(f"  노드: {before_nodes} → {len(graph['nodes'])} ({before_nodes - len(graph['nodes'])}개 제거)")
    print(f"  링크: {before_links} → {len(graph['links'])} ({before_links - len(graph['links'])}개 제거)")

    # 저장
    from core.graph_utils import save_graph
    save_graph(graph, str(GRAPH_PATH))

    # 파이프라인 완료 마커(marker) 생성
    marker = BASE_DIR / "data" / "output" / ".dedup_done"
    marker.touch()

    print(f"\n저장: {GRAPH_PATH}")
    print("  enrich_graph.py를 재실행하여 data.json을 갱신하세요.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="의미 기반 중복 노드 탐지/병합")
    parser.add_argument("--apply", action="store_true", help="병합을 실제로 적용")
    parser.add_argument("--no-llm", action="store_true", help="LLM 확인 없이 규칙만 사용")
    args = parser.parse_args()
    run(apply=args.apply, use_llm=not args.no_llm)
