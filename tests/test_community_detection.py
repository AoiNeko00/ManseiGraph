"""core/community_detection.py 단위 테스트."""

from core.community_detection import (
    build_igraph,
    compute_modularity,
    detect_communities,
    get_community_links,
    group_communities,
    merge_small_communities,
)


def test_build_igraph(sample_graph):
    """igraph 변환 정상 동작 검증."""
    ig_graph, node_ids = build_igraph(sample_graph)

    assert ig_graph.vcount() == len(sample_graph["nodes"])
    assert ig_graph.ecount() == len(sample_graph["links"])
    assert "kim_gu" in node_ids


def test_detect_communities(sample_graph):
    """커뮤니티 탐지 결과 형식 검증."""
    membership = detect_communities(sample_graph)

    # 모든 노드에 커뮤니티가 할당되어야 함
    for node in sample_graph["nodes"]:
        assert node["id"] in membership

    # 최소 1개 커뮤니티 존재
    assert len(set(membership.values())) >= 1


def test_compute_modularity(sample_graph):
    """모듈러리티 범위 검증 (-0.5 ~ 1.0)."""
    membership = detect_communities(sample_graph)
    modularity = compute_modularity(sample_graph, membership)

    assert -0.5 <= modularity <= 1.0


def test_group_communities(sample_graph):
    """커뮤니티 그룹핑 정확도 검증."""
    membership = detect_communities(sample_graph)
    groups = group_communities(sample_graph, membership)

    # 모든 노드가 어딘가에 속해야 함
    total = sum(len(nodes) for nodes in groups.values())
    assert total == len(sample_graph["nodes"])


def test_get_community_links(sample_graph):
    """커뮤니티 내부 링크 추출 검증."""
    membership = detect_communities(sample_graph)
    # 아무 커뮤니티나 선택
    comm_idx = list(set(membership.values()))[0]
    links = get_community_links(sample_graph, membership, comm_idx)

    # 반환된 링크의 source/target이 모두 해당 커뮤니티 소속이어야 함
    comm_nodes = {nid for nid, idx in membership.items() if idx == comm_idx}
    for link in links:
        assert link["source"] in comm_nodes
        assert link["target"] in comm_nodes


def test_merge_small_communities(sample_graph):
    """소규모 커뮤니티 병합 검증."""
    membership = detect_communities(sample_graph)
    merged = merge_small_communities(membership, sample_graph, min_size=3)

    # 병합 후에도 모든 노드가 할당되어야 함
    assert set(merged.keys()) == set(membership.keys())
