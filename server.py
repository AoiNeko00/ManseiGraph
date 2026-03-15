#!/usr/bin/env python3
"""GraphRAG 검색 API 서버.

Local Search와 Global Search 엔드포인트를 제공한다.
프론트엔드에서 자연어 질의를 보내면 그래프 기반 답변을 반환한다.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.graph_utils import load_graph
from core.search_engine import drift_search, global_search, local_search

BASE_DIR = Path(__file__).resolve().parent
_GRAPH_ADVANCED = BASE_DIR / "data" / "output" / "graph_advanced.json"
_GRAPH_DEFAULT = BASE_DIR / "data" / "output" / "graph.json"
GRAPH_PATH = _GRAPH_ADVANCED if _GRAPH_ADVANCED.exists() else _GRAPH_DEFAULT
DATA_JSON = BASE_DIR / "frontend" / "src" / "data.json"

app = FastAPI(title="ManseiGraph Search API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 그래프 데이터 로드 (서버 시작 시 1회)
_graph = None


def _get_graph() -> dict:
    """그래프 데이터를 로드한다 (lazy loading)."""
    global _graph
    if _graph is None:
        # data.json 우선 사용 (enriched 데이터)
        path = str(DATA_JSON) if DATA_JSON.exists() else str(GRAPH_PATH)
        _graph = load_graph(path)
    return _graph


class SearchRequest(BaseModel):
    query: str
    search_type: str = "local"  # "local", "global", 또는 "drift"


class SearchResponse(BaseModel):
    answer: str
    activated_nodes: list[str] = []
    activated_communities: list[str] = []
    search_type: str = ""


@app.post("/api/search", response_model=SearchResponse)
def search(request: SearchRequest):
    """자연어 질의를 받아 그래프 기반 답변을 반환한다."""
    graph = _get_graph()

    if request.search_type == "global":
        result = global_search(request.query, graph=graph)
        return SearchResponse(
            answer=result["answer"],
            activated_nodes=result.get("activated_nodes", []),
            activated_communities=result.get("activated_communities", []),
            search_type="global",
        )

    if request.search_type == "drift":
        result = drift_search(request.query, graph)
        return SearchResponse(
            answer=result["answer"],
            activated_nodes=result.get("activated_nodes", []),
            activated_communities=result.get("activated_communities", []),
            search_type="drift",
        )

    result = local_search(request.query, graph)
    return SearchResponse(
        answer=result["answer"],
        activated_nodes=result.get("activated_nodes", []),
        activated_communities=result.get("activated_communities", []),
        search_type="local",
    )


@app.get("/api/claims/{entity_name}")
def get_claims(entity_name: str):
    """특정 엔티티의 Claims를 반환한다."""
    claims_path = BASE_DIR / "data" / "output" / "claims.json"
    if not claims_path.exists():
        return {"claims": []}

    import json
    with open(claims_path, encoding="utf-8") as f:
        all_claims = json.load(f)

    # 이름 매칭 (괄호 앞 부분)
    base_name = entity_name.split("(")[0].strip()
    claims = all_claims.get(base_name, all_claims.get(entity_name, []))
    return {"claims": claims}


@app.get("/api/health")
def health():
    """헬스체크 엔드포인트."""
    graph = _get_graph()
    return {
        "status": "ok",
        "nodes": len(graph.get("nodes", [])),
        "links": len(graph.get("links", [])),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
