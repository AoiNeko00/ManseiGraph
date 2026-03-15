"""임베딩(embedding) 모듈.

노드 텍스트를 벡터로 변환하고 코사인 유사도 기반 의미 검색을 제공한다.
"""

import json
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
EMBEDDINGS_PATH = BASE_DIR / "data" / "output" / "embeddings.npz"
INDEX_PATH = BASE_DIR / "data" / "output" / "embedding_index.json"

# 다국어(multilingual) 경량 임베딩 모델
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


def build_node_text(node: dict) -> str:
    """노드의 검색용 텍스트를 생성한다.

    이름, 설명, 커뮤니티 정보를 결합하여 풍부한 임베딩 입력을 만든다.
    """
    parts = [node.get("name", "")]
    if node.get("description"):
        parts.append(node["description"])
    if node.get("communityName"):
        parts.append(node["communityName"])
    return " ".join(parts)


def generate_embeddings(graph: dict) -> tuple[np.ndarray, list[str]]:
    """모든 노드의 임베딩을 생성한다.

    Args:
        graph: {"nodes": [...]} 형태의 그래프 데이터.

    Returns:
        (embeddings_matrix, node_ids): (N x dim) 행렬과 노드 ID 리스트.
    """
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME)

    node_ids = []
    texts = []
    for node in graph["nodes"]:
        node_ids.append(node["id"])
        texts.append(build_node_text(node))

    print(f"  {len(texts)}개 노드 임베딩 생성 중...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)

    return np.array(embeddings, dtype=np.float32), node_ids


def save_embeddings(
    embeddings: np.ndarray,
    node_ids: list[str],
) -> None:
    """임베딩을 파일에 저장한다."""
    EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(EMBEDDINGS_PATH, embeddings=embeddings)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(node_ids, f, ensure_ascii=False)


def load_embeddings() -> tuple[np.ndarray, list[str]] | None:
    """저장된 임베딩을 로드한다. 없으면 None 반환."""
    if not EMBEDDINGS_PATH.exists() or not INDEX_PATH.exists():
        return None
    data = np.load(EMBEDDINGS_PATH)
    with open(INDEX_PATH, encoding="utf-8") as f:
        node_ids = json.load(f)
    return data["embeddings"], node_ids


def generate_report_embeddings(reports: list[dict]) -> np.ndarray:
    """커뮤니티 리포트의 summary를 임베딩한다.

    Args:
        reports: 커뮤니티 리포트 리스트 (summary 필드 필요).

    Returns:
        (N x dim) 임베딩 행렬.
    """
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME)
    texts = [r.get("summary", r.get("title", "")) for r in reports]
    return np.array(model.encode(texts, batch_size=32), dtype=np.float32)


def rank_reports_by_query(
    query: str,
    reports: list[dict],
    top_k: int = 10,
) -> list[dict]:
    """질의와 유사도가 높은 리포트를 정렬하여 반환한다.

    Args:
        query: 검색 질의.
        reports: 커뮤니티 리포트 리스트.
        top_k: 반환할 상위 리포트 수.

    Returns:
        유사도 내림차순으로 정렬된 리포트 리스트.
    """
    if not reports:
        return []

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME)
    query_emb = model.encode([query], normalize_embeddings=True)[0]
    report_embs = generate_report_embeddings(reports)

    norms = np.linalg.norm(report_embs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized = report_embs / norms

    similarities = normalized @ query_emb
    top_indices = np.argsort(similarities)[::-1][:top_k]

    return [reports[i] for i in top_indices if similarities[i] > 0.05]


def semantic_search(
    query: str,
    embeddings: np.ndarray,
    node_ids: list[str],
    top_k: int = 10,
) -> list[tuple[str, float]]:
    """코사인 유사도(cosine similarity) 기반 의미 검색을 수행한다.

    Args:
        query: 검색 질의 문자열.
        embeddings: (N x dim) 노드 임베딩 행렬.
        node_ids: 노드 ID 리스트 (embeddings와 동일 순서).
        top_k: 반환할 상위 결과 수.

    Returns:
        [(node_id, similarity_score), ...] 유사도 내림차순 정렬.
    """
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME)
    query_emb = model.encode([query], normalize_embeddings=True)[0]

    # 정규화된 임베딩으로 코사인 유사도 계산
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1  # 0벡터 방지
    normalized = embeddings / norms

    similarities = normalized @ query_emb
    top_indices = np.argsort(similarities)[::-1][:top_k]

    return [
        (node_ids[i], float(similarities[i]))
        for i in top_indices
        if similarities[i] > 0.1  # 최소 유사도 임계값(threshold)
    ]
