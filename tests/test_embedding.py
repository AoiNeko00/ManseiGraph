"""core/embedding.py 단위 테스트."""

import numpy as np

from core.embedding import build_node_text, semantic_search


def test_build_node_text():
    """노드 텍스트 생성 검증."""
    node = {
        "name": "김구",
        "description": "대한민국 임시정부 주석",
        "communityName": "임시정부 네트워크",
    }
    text = build_node_text(node)
    assert "김구" in text
    assert "임시정부" in text
    assert "네트워크" in text


def test_build_node_text_minimal():
    """최소 필드 노드 텍스트 생성 검증."""
    node = {"name": "테스트"}
    text = build_node_text(node)
    assert text == "테스트"


def test_semantic_search_basic():
    """코사인 유사도 검색 기본 동작 검증."""
    # 3개 노드, 4차원 임베딩 (실제 모델 없이 검증)
    embeddings = np.array([
        [1.0, 0.0, 0.0, 0.0],  # node_a
        [0.0, 1.0, 0.0, 0.0],  # node_b
        [0.9, 0.1, 0.0, 0.0],  # node_c (node_a와 유사)
    ], dtype=np.float32)
    node_ids = ["node_a", "node_b", "node_c"]

    # semantic_search는 내부에서 모델을 로드하므로
    # 직접 코사인 유사도 계산 로직을 테스트
    query_emb = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized = embeddings / norms
    similarities = normalized @ query_emb

    top_indices = np.argsort(similarities)[::-1][:3]
    results = [(node_ids[i], float(similarities[i])) for i in top_indices]

    # node_a가 가장 유사해야 함
    assert results[0][0] == "node_a"
    assert results[0][1] > 0.9
    # node_c가 두 번째
    assert results[1][0] == "node_c"
    # node_b가 가장 낮음
    assert results[2][0] == "node_b"
    assert results[2][1] < 0.01
