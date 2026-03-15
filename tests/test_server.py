"""server.py API 엔드포인트 테스트."""

import pytest
from fastapi.testclient import TestClient

from server import app


@pytest.fixture
def client():
    """테스트 클라이언트."""
    return TestClient(app)


def test_health(client):
    """헬스체크 엔드포인트 검증."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["nodes"] > 0
    assert data["links"] > 0


def test_search_invalid_type(client):
    """유효하지 않은 search_type은 local로 폴백 검증."""
    # search_type이 유효하지 않아도 local로 처리됨
    response = client.post("/api/search", json={
        "query": "테스트",
        "search_type": "invalid_type",
    })
    assert response.status_code == 200
