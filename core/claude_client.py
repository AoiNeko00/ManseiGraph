"""Claude CLI 클라이언트(client) 모듈.

subprocess를 통해 claude CLI를 호출하고, JSON 응답을 파싱하는 함수를 제공한다.
"""

import json
import os
import subprocess
import time

MAX_RETRIES = 3          # 최대 재시도(retry) 횟수
CALL_TIMEOUT = 600       # subprocess 타임아웃(timeout, 초) — 10분


def call_claude(prompt: str, timeout: int | None = None) -> str:
    """claude --print 명령어를 subprocess로 호출하여 응답을 받는다.

    타임아웃 또는 일시적 오류 시 최대 MAX_RETRIES회 재시도한다.

    Args:
        prompt: Claude에 전달할 프롬프트 문자열.
        timeout: subprocess 타임아웃(초). None이면 CALL_TIMEOUT 사용.
    """
    effective_timeout = timeout if timeout is not None else CALL_TIMEOUT

    # 중첩 세션(nested session) 방지를 위해 CLAUDECODE 환경변수 제거
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = subprocess.run(
                ["claude", "--print", "--model", "opus", "--output-format", "json"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                env=env,
            )
            if result.returncode != 0:
                err_msg = result.stderr.strip()
                # 재시도 가능한 오류(rate limit, 서버 오류 등)
                if attempt < MAX_RETRIES and ("rate" in err_msg.lower() or "overloaded" in err_msg.lower() or "500" in err_msg or "529" in err_msg):
                    wait = 30 * attempt
                    print(f"    [재시도 {attempt}/{MAX_RETRIES}] {wait}초 대기 ({err_msg[:80]})")
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"claude CLI 오류: {err_msg}")
            return result.stdout
        except subprocess.TimeoutExpired:
            if attempt < MAX_RETRIES:
                wait = 30 * attempt
                print(f"    [타임아웃 재시도 {attempt}/{MAX_RETRIES}] {wait}초 대기")
                time.sleep(wait)
                continue
            raise RuntimeError(f"claude CLI 타임아웃 ({effective_timeout}초 초과, {MAX_RETRIES}회 시도)")
    raise RuntimeError("call_claude: 최대 재시도 초과")


def parse_claude_response(raw: str) -> dict:
    """claude CLI의 JSON 출력에서 엔티티/관계 데이터를 파싱(parsing)한다."""
    try:
        outer = json.loads(raw)
        content = outer.get("result", raw)
    except json.JSONDecodeError:
        content = raw

    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]

    start = content.find("{")
    end = content.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"JSON을 찾을 수 없습니다: {content[:200]}")

    return json.loads(content[start:end])
