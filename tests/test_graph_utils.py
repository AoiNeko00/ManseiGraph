"""core/graph_utils.py 단위 테스트."""

from core.graph_utils import (
    build_node_index,
    compute_degree,
    find_isolated_nodes,
)


def test_build_node_index(sample_graph):
    """노드 인덱스 구축 정상 동작 검증."""
    index = build_node_index(sample_graph)
    assert "kim_gu" in index
    assert index["kim_gu"]["name"] == "김구"
    assert len(index) == len(sample_graph["nodes"])


def test_compute_degree(sample_graph):
    """degree 재계산 정확도 검증."""
    compute_degree(sample_graph)
    index = build_node_index(sample_graph)

    # 김구: led(provisional_govt) + collaborated_with(lee_seungman) + influenced(an_junggeun) = 3
    assert index["kim_gu"]["degree"] == 3
    # 고립 노드: 0
    assert index["isolated_node"]["degree"] == 0
    # 임시정부: led(kim_gu) + member_of(lee_seungman) + located_in(shanghai) + led_to(march_first) = 4
    assert index["provisional_govt"]["degree"] == 4


def test_find_isolated_nodes(sample_graph):
    """고립 노드 탐지 검증."""
    isolated = find_isolated_nodes(sample_graph)
    ids = [n["id"] for n in isolated]
    assert "isolated_node" in ids
    assert "kim_gu" not in ids
