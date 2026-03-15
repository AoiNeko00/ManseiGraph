#!/usr/bin/env python3
"""노드 임베딩 사전 생성(pre-build embeddings) 스크립트.

모든 노드의 텍스트를 벡터화하여 저장한다.
이후 검색 시 실시간 임베딩 생성 없이 유사도 계산만 수행한다.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.embedding import generate_embeddings, save_embeddings
from core.graph_utils import load_graph

_DATA_JSON = BASE_DIR / "frontend" / "src" / "data.json"
_GRAPH_ADVANCED = BASE_DIR / "data" / "output" / "graph_advanced.json"
GRAPH_PATH = _DATA_JSON if _DATA_JSON.exists() else _GRAPH_ADVANCED


def run() -> None:
    """임베딩을 생성하고 저장한다."""
    print("=== 노드 임베딩 생성 시작 ===")

    graph = load_graph(str(GRAPH_PATH))
    print(f"입력: {len(graph['nodes'])}개 노드")

    embeddings, node_ids = generate_embeddings(graph)
    print(f"임베딩 생성 완료: shape={embeddings.shape}")

    save_embeddings(embeddings, node_ids)
    print(f"저장 완료: embeddings.npz + embedding_index.json")


if __name__ == "__main__":
    run()
