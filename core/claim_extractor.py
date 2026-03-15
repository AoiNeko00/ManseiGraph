"""Claim 추출(claim extraction) 모듈.

엔티티에 대한 역사적 주장/사실을 추출하고 파싱한다.
"""

import re
from pathlib import Path

from core.claude_client import call_claude

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extract_claims.txt"


def load_claim_prompt() -> str:
    """Claim 추출 프롬프트를 로드한다."""
    with open(PROMPT_PATH, encoding="utf-8") as f:
        return f.read()


def extract_claims_from_text(
    text: str,
    entity_specs: str = "person",
    claim_description: str = "historical acts and roles associated with an entity",
) -> list[dict]:
    """텍스트에서 Claim을 추출한다.

    Args:
        text: 원본 텍스트.
        entity_specs: 추출 대상 엔티티 타입 또는 이름 목록.
        claim_description: Claim 설명.

    Returns:
        [{"subject": str, "object": str, "claim_type": str,
          "status": str, "start_date": str, "end_date": str,
          "description": str, "source_text": str}, ...]
    """
    template = load_claim_prompt()
    prompt = (
        template
        .replace("{entity_specs}", entity_specs)
        .replace("{claim_description}", claim_description)
        .replace("{input_text}", text[:80000])
    )

    raw = call_claude(prompt)
    return parse_claims(raw)


def parse_claims(raw: str) -> list[dict]:
    """LLM 응답에서 Claim을 파싱한다.

    형식: (subject<|>object<|>claim_type<|>status<|>start<|>end<|>desc<|>source)
    구분자: ##
    """
    import json

    # JSON wrapper 제거
    try:
        outer = json.loads(raw)
        content = outer.get("result", raw)
    except (json.JSONDecodeError, TypeError):
        content = raw

    # <|COMPLETE|> 이후 제거
    content = content.split("<|COMPLETE|>")[0]

    claims = []
    for segment in content.split("##"):
        segment = segment.strip()
        if not segment:
            continue

        # 괄호 제거
        segment = segment.strip("()")

        parts = segment.split("<|>")
        if len(parts) < 7:
            continue

        claim = {
            "subject": parts[0].strip(),
            "object": parts[1].strip(),
            "claim_type": parts[2].strip(),
            "status": parts[3].strip(),
            "start_date": parts[4].strip() if len(parts) > 4 else "NONE",
            "end_date": parts[5].strip() if len(parts) > 5 else "NONE",
            "description": parts[6].strip() if len(parts) > 6 else "",
            "source_text": parts[7].strip() if len(parts) > 7 else "",
        }
        claims.append(claim)

    return claims
