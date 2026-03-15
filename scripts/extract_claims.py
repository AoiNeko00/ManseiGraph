#!/usr/bin/env python3
"""Claim 추출 실행 스크립트.

그래프의 주요 인물 노드에 대해 원본 텍스트에서 Claims를 추출한다.
결과는 claims.json에 저장된다.
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.claim_extractor import extract_claims_from_text
from core.graph_utils import load_graph
from core.text_utils import read_input_file

INPUT_DIR = BASE_DIR / "data" / "input"
_GRAPH_ADVANCED = BASE_DIR / "data" / "output" / "graph_advanced.json"
_GRAPH_DEFAULT = BASE_DIR / "data" / "output" / "graph.json"
GRAPH_PATH = _GRAPH_ADVANCED if _GRAPH_ADVANCED.exists() else _GRAPH_DEFAULT
OUTPUT_PATH = BASE_DIR / "data" / "output" / "claims.json"

# 상위 N명의 주요 인물에 대해 추출 (LLM 호출 비용 제한)
MAX_ENTITIES = 20


def run() -> None:
    """주요 인물의 Claims를 추출한다."""
    print("=== Claim 추출 시작 ===")

    graph = load_graph(str(GRAPH_PATH))

    # 기존 claims 캐시 로드
    existing_claims: dict[str, list[dict]] = {}
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            existing_claims = json.load(f)
        print(f"기존 claims {len(existing_claims)}개 엔티티 로드됨")

    # degree 상위 person 노드 선택
    persons = [
        n for n in graph["nodes"]
        if n["type"] == "person"
    ]
    persons.sort(key=lambda n: -n.get("degree", 0))
    targets = persons[:MAX_ENTITIES]

    print(f"대상: {len(targets)}명 (degree 상위)")

    # 입력 텍스트 파일 로드
    input_texts = {}
    for p in INPUT_DIR.glob("*.txt"):
        input_texts[p.stem] = read_input_file(str(p))

    all_text = "\n\n".join(input_texts.values())

    for node in targets:
        name = node["name"]
        if name in existing_claims:
            print(f"  [캐시] {name}: {len(existing_claims[name])}개 claims")
            continue

        # 해당 인물이 언급된 텍스트 추출
        relevant_text = _find_relevant_text(name, input_texts)
        if not relevant_text:
            print(f"  [건너뜀] {name}: 관련 텍스트 없음")
            continue

        print(f"  {name}: 추출 중...")
        claims = extract_claims_from_text(
            relevant_text,
            entity_specs=name,
        )
        existing_claims[name] = claims
        print(f"    → {len(claims)}개 claims 추출")

        # 중간 저장
        _save_claims(existing_claims)

    _save_claims(existing_claims)
    total = sum(len(v) for v in existing_claims.values())
    print(f"\n=== Claim 추출 완료: {len(existing_claims)}명, 총 {total}개 claims ===")


def _find_relevant_text(name: str, input_texts: dict[str, str]) -> str:
    """인물 관련 텍스트를 추출한다 (최대 40,000자)."""
    parts = []
    for fname, content in input_texts.items():
        if name in content:
            parts.append(content)
    combined = "\n\n".join(parts)
    return combined[:40000] if combined else ""


def _save_claims(claims: dict[str, list[dict]]) -> None:
    """Claims를 JSON으로 저장한다."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(claims, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    run()
