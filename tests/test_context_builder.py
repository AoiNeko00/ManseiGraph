"""core/context_builder.py 단위 테스트."""

from core.context_builder import (
    _compute_relevance_score,
    _find_by_keyword,
    build_local_context,
)


def test_compute_relevance_score_exact_match():
    """이름 완전 일치 시 높은 점수 검증."""
    node = {"name": "김구", "description": "임시정부 주석", "degree": 10}
    score = _compute_relevance_score(node, "김구", {"김구"})
    assert score >= 10.0


def test_compute_relevance_score_no_match():
    """무관한 질의 시 0점 검증."""
    node = {"name": "김구", "description": "임시정부 주석", "degree": 10}
    score = _compute_relevance_score(node, "축구", {"축구"})
    assert score == 0.0


def test_compute_relevance_score_partial_match():
    """설명 키워드 매칭 검증."""
    node = {"name": "이승만", "description": "외교독립론 주장", "degree": 5}
    score = _compute_relevance_score(node, "외교를 통한 독립", {"외교를", "통한", "독립"})
    assert score > 0


def test_find_by_keyword(sample_graph):
    """키워드 검색 결과 검증."""
    results = _find_by_keyword("김구", sample_graph, max_entities=5)
    assert len(results) > 0
    assert results[0]["name"] == "김구"


def test_find_by_keyword_empty(sample_graph):
    """매칭 없는 질의 시 빈 리스트 검증."""
    results = _find_by_keyword("존재하지않는키워드xyz", sample_graph, max_entities=5)
    assert len(results) == 0


def test_build_local_context(sample_graph):
    """로컬 컨텍스트 형식 검증."""
    context = build_local_context("김구", sample_graph)
    assert "---Entities---" in context
    assert "---Relationships---" in context
    assert "김구" in context


def test_build_local_context_empty(sample_graph):
    """매칭 없는 질의 시 빈 컨텍스트 검증."""
    context = build_local_context("존재하지않는xyz", sample_graph)
    assert context == ""
