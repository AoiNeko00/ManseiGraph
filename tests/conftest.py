"""테스트 공통 픽스처(fixture) 정의."""

import pytest


@pytest.fixture
def sample_graph():
    """테스트용 소규모 그래프 데이터."""
    return {
        "nodes": [
            {"id": "kim_gu", "name": "김구", "type": "person",
             "description": "대한민국 임시정부 주석", "degree": 10,
             "communityId": "c1", "communityName": "임시정부 네트워크"},
            {"id": "lee_seungman", "name": "이승만", "type": "person",
             "description": "대한민국 초대 대통령, 외교독립론", "degree": 8,
             "communityId": "c1", "communityName": "임시정부 네트워크"},
            {"id": "an_junggeun", "name": "안중근", "type": "person",
             "description": "이토 히로부미를 저격한 의사", "degree": 6,
             "communityId": "c2", "communityName": "의열투쟁 네트워크"},
            {"id": "provisional_govt", "name": "대한민국 임시정부", "type": "organization",
             "description": "1919년 상하이에서 수립된 독립운동 정부", "degree": 15,
             "communityId": "c1", "communityName": "임시정부 네트워크"},
            {"id": "march_first", "name": "3·1운동", "type": "event",
             "description": "1919년 전국적 만세운동", "degree": 12,
             "communityId": "c3", "communityName": "만세운동 네트워크"},
            {"id": "shanghai", "name": "상하이", "type": "location",
             "description": "임시정부 소재지", "degree": 5,
             "communityId": "c1", "communityName": "임시정부 네트워크"},
            {"id": "isolated_node", "name": "고립노드", "type": "concept",
             "description": "연결이 없는 테스트 노드", "degree": 0,
             "communityId": "uncategorized", "communityName": "기타"},
        ],
        "links": [
            {"source": "kim_gu", "target": "provisional_govt",
             "weight": 1, "relation": "led", "description": "주석으로 지도"},
            {"source": "lee_seungman", "target": "provisional_govt",
             "weight": 1, "relation": "member_of", "description": "초대 대통령"},
            {"source": "kim_gu", "target": "lee_seungman",
             "weight": 1, "relation": "collaborated_with", "description": "독립운동 협력"},
            {"source": "provisional_govt", "target": "shanghai",
             "weight": 1, "relation": "located_in", "description": "소재지"},
            {"source": "march_first", "target": "provisional_govt",
             "weight": 1, "relation": "led_to", "description": "수립 계기"},
            {"source": "an_junggeun", "target": "kim_gu",
             "weight": 1, "relation": "influenced", "description": "정신적 영향"},
        ],
    }
