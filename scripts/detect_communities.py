#!/usr/bin/env python3
"""커뮤니티 자동 탐지(community detection) 실행 스크립트.

Leiden 알고리즘으로 커뮤니티를 탐지하고,
기존 수동 커뮤니티와 비교 검증한 뒤 결과를 저장한다.
"""

import json
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.community_detection import (
    compute_modularity,
    detect_communities,
    group_communities,
    merge_small_communities,
)
from core.graph_utils import load_graph
from scripts.enrich_constants import COMMUNITIES

# ─── 경로 설정 ───

_GRAPH_ADVANCED = BASE_DIR / "data" / "output" / "graph_advanced.json"
_GRAPH_DEFAULT = BASE_DIR / "data" / "output" / "graph.json"
GRAPH_PATH = _GRAPH_ADVANCED if _GRAPH_ADVANCED.exists() else _GRAPH_DEFAULT
OUTPUT_PATH = BASE_DIR / "data" / "output" / "communities.json"


def label_community(nodes: list[dict], manual_communities: dict) -> dict:
    """Leiden 커뮤니티에 의미 있는 라벨을 부여한다.

    기존 수동 커뮤니티와 노드 겹침률을 비교하여 가장 유사한 라벨을 할당한다.
    겹침이 없으면 대표 노드 기반으로 라벨을 생성한다.
    """
    node_ids = {n["id"] for n in nodes}

    best_match_id = None
    best_overlap = 0

    for comm_id, comm in manual_communities.items():
        manual_ids = set(comm["node_ids"])
        overlap = len(node_ids & manual_ids)
        if overlap > best_overlap:
            best_overlap = overlap
            best_match_id = comm_id

    # 겹침률이 20% 이상이면 기존 라벨 사용
    if best_match_id and best_overlap >= max(1, len(node_ids) * 0.2):
        comm = manual_communities[best_match_id]
        return {
            "id": best_match_id,
            "name": comm["name"],
            "matched_from": "manual",
            "overlap_count": best_overlap,
        }

    # 대표 노드 기반 라벨 생성
    top_nodes = sorted(nodes, key=lambda n: -n.get("degree", 0))[:3]
    names = [n["name"] for n in top_nodes]
    label = " · ".join(names) + " 네트워크"
    comm_id = f"auto_{top_nodes[0]['id']}" if top_nodes else "auto_unknown"

    return {
        "id": comm_id,
        "name": label,
        "matched_from": "auto",
        "overlap_count": 0,
    }


def run_detection(resolution: float = 1.0) -> dict:
    """커뮤니티 탐지를 실행하고 결과를 저장한다."""
    print(f"=== Leiden 커뮤니티 탐지 시작 (resolution={resolution}) ===")

    graph = load_graph(str(GRAPH_PATH))
    print(f"입력: {len(graph['nodes'])}개 노드, {len(graph['links'])}개 링크")

    # Leiden 알고리즘 실행
    membership = detect_communities(graph, resolution=resolution)
    modularity_raw = compute_modularity(graph, membership)
    print(f"모듈러리티(modularity, 병합 전): {modularity_raw:.4f}")

    # 소규모 커뮤니티 병합 (3개 미만 → 이웃 커뮤니티에 흡수)
    raw_count = len(set(membership.values()))
    membership = merge_small_communities(membership, graph, min_size=3)
    modularity = compute_modularity(graph, membership)
    merged_count = raw_count - len(set(membership.values()))
    print(f"소규모 커뮤니티 병합: {merged_count}개 병합됨")
    print(f"모듈러리티(modularity, 병합 후): {modularity:.4f}")

    # 커뮤니티 그룹핑
    groups = group_communities(graph, membership)
    print(f"탐지된 커뮤니티 수: {len(groups)}개")

    # 각 커뮤니티에 라벨 부여
    communities = []
    for comm_idx, nodes in sorted(groups.items(), key=lambda x: -len(x[1])):
        # 고립 노드 커뮤니티 (-1) 특별 처리
        if comm_idx == -1:
            community = {
                "index": comm_idx,
                "id": "uncategorized",
                "name": "기타 독립운동 관련",
                "matched_from": "isolated",
                "node_count": len(nodes),
                "node_ids": [n["id"] for n in nodes],
            }
            communities.append(community)
            print(f"  [고립] 기타 독립운동 관련: {len(nodes)}개 노드 (고립 병합)")
            continue

        label_info = label_community(nodes, COMMUNITIES)
        community = {
            "index": comm_idx,
            "id": label_info["id"],
            "name": label_info["name"],
            "matched_from": label_info["matched_from"],
            "node_count": len(nodes),
            "node_ids": [n["id"] for n in nodes],
        }
        communities.append(community)
        print(f"  [{comm_idx}] {label_info['name']}: {len(nodes)}개 노드"
              f" ({label_info['matched_from']})")

    # 노드→커뮤니티 매핑 저장
    result = {
        "resolution": resolution,
        "modularity": modularity,
        "community_count": len(communities),
        "membership": membership,
        "communities": communities,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {OUTPUT_PATH}")

    # 기존 수동 커뮤니티와 일치율 보고
    _report_match_rate(membership, COMMUNITIES)

    return result


def _report_match_rate(
    membership: dict[str, int],
    manual_communities: dict,
) -> None:
    """기존 수동 커뮤니티와 Leiden 결과의 일치율을 보고한다."""
    print("\n=== 수동 커뮤니티 vs Leiden 일치율 ===")
    for comm_id, comm in manual_communities.items():
        manual_ids = set(comm["node_ids"])
        # 수동 커뮤니티 노드들이 Leiden에서 같은 커뮤니티에 속하는 비율
        leiden_assignments = {}
        for nid in manual_ids:
            if nid in membership:
                lidx = membership[nid]
                leiden_assignments[lidx] = leiden_assignments.get(lidx, 0) + 1

        if not leiden_assignments:
            print(f"  {comm['name']}: 매칭 노드 없음")
            continue

        dominant_idx = max(leiden_assignments, key=leiden_assignments.get)
        dominant_count = leiden_assignments[dominant_idx]
        matched_count = sum(1 for nid in manual_ids if nid in membership)
        coherence = dominant_count / matched_count if matched_count else 0

        print(f"  {comm['name']}: "
              f"일치율 {coherence:.0%} "
              f"({dominant_count}/{matched_count}개가 Leiden #{dominant_idx}에 집중)")


def _build_hierarchy_links(levels: list[dict]) -> None:
    """레벨 간 포함 관계(parent-child)를 매핑하여 각 커뮤니티에 children/parent 필드를 추가한다.

    하위 레벨 커뮤니티의 노드 집합이 상위 레벨 커뮤니티에 가장 많이 겹치는 쪽을 parent로 지정한다.
    """
    for i in range(len(levels) - 1):
        parent_level = levels[i]
        child_level = levels[i + 1]

        # 상위 커뮤니티별 노드 집합
        parent_node_sets = {}
        for comm in parent_level["communities"]:
            parent_node_sets[comm["id"]] = set(comm.get("node_ids", []))

        # 하위 커뮤니티별 parent 매핑
        for child_comm in child_level["communities"]:
            child_nodes = set(child_comm.get("node_ids", []))
            if not child_nodes:
                continue

            best_parent = None
            best_overlap = 0
            for parent_id, parent_nodes in parent_node_sets.items():
                overlap = len(child_nodes & parent_nodes)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_parent = parent_id

            child_comm["parent_community_id"] = best_parent

        # 상위 커뮤니티에 children 리스트 추가
        for parent_comm in parent_level["communities"]:
            parent_comm["children"] = [
                c["id"] for c in child_level["communities"]
                if c.get("parent_community_id") == parent_comm["id"]
            ]

    print(f"\n계층 포함 관계 매핑 완료:")
    for level_data in levels:
        level = level_data["level"]
        for comm in level_data["communities"]:
            children = comm.get("children", [])
            parent = comm.get("parent_community_id", "")
            if children:
                print(f"  L{level} {comm['name']} → children: {len(children)}개")
            elif parent:
                print(f"  L{level} {comm['name']} → parent: {parent}")


def run_hierarchical_detection(
    resolutions: list[float] | None = None,
) -> dict:
    """다중 해상도로 계층적 커뮤니티를 탐지한다.

    기존 단일 레벨 결과(membership, communities)는 Level 1(resolution=1.0)로 유지하여
    하위 호환성을 보장하고, levels 필드에 전체 계층을 추가한다.
    """
    if resolutions is None:
        resolutions = [0.3, 1.0, 2.5]

    print(f"=== 계층적 커뮤니티 탐지 시작 (resolutions={resolutions}) ===")
    graph = load_graph(str(GRAPH_PATH))
    print(f"입력: {len(graph['nodes'])}개 노드, {len(graph['links'])}개 링크")

    levels = []
    primary_result = None

    for level_idx, res in enumerate(resolutions):
        print(f"\n--- Level {level_idx} (resolution={res}) ---")
        membership = detect_communities(graph, resolution=res)
        membership = merge_small_communities(membership, graph, min_size=3)
        modularity = compute_modularity(graph, membership)

        groups = group_communities(graph, membership)

        communities = []
        for comm_idx, nodes in sorted(groups.items(), key=lambda x: -len(x[1])):
            if comm_idx == -1:
                communities.append({
                    "index": comm_idx, "id": "uncategorized",
                    "name": "기타 독립운동 관련", "matched_from": "isolated",
                    "node_count": len(nodes),
                    "node_ids": [n["id"] for n in nodes],
                })
                continue
            label_info = label_community(nodes, COMMUNITIES)
            communities.append({
                "index": comm_idx, "id": label_info["id"],
                "name": label_info["name"], "matched_from": label_info["matched_from"],
                "node_count": len(nodes),
                "node_ids": [n["id"] for n in nodes],
            })

        level_data = {
            "level": level_idx,
            "resolution": res,
            "modularity": modularity,
            "community_count": len(communities),
            "membership": membership,
            "communities": communities,
        }
        levels.append(level_data)
        print(f"  커뮤니티: {len(communities)}개, 모듈러리티: {modularity:.4f}")

        # resolution=1.0에 가장 가까운 레벨을 기본 레벨로 사용
        if res == 1.0 or (primary_result is None and level_idx == len(resolutions) - 1):
            primary_result = level_data

    # 계층 간 포함 관계(parent-child) 매핑
    _build_hierarchy_links(levels)

    # 기존 포맷 호환: 기본 레벨의 membership/communities를 최상위에 유지
    result = {
        "resolution": primary_result["resolution"],
        "modularity": primary_result["modularity"],
        "community_count": primary_result["community_count"],
        "membership": primary_result["membership"],
        "communities": primary_result["communities"],
        "levels": levels,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {OUTPUT_PATH}")
    print(f"  Level 0 (대분류): {levels[0]['community_count']}개")
    print(f"  Level 1 (기본): {levels[1]['community_count']}개")
    print(f"  Level 2 (세분류): {levels[2]['community_count']}개")

    return result


if __name__ == "__main__":
    if "--hierarchical" in sys.argv:
        run_hierarchical_detection()
    else:
        resolution = 1.0
        for arg in sys.argv[1:]:
            try:
                resolution = float(arg)
                break
            except ValueError:
                continue
        run_detection(resolution)
