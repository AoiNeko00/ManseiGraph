"""텍스트 처리(text processing) 유틸리티 모듈.

파일 읽기, 텍스트 청킹, ID 정규화 등의 함수를 제공한다.
"""

from core.constants import CHUNK_OVERLAP, MAX_TEXT_LENGTH


def normalize_id(name: str) -> str:
    """엔티티 ID를 정규화(normalize)한다."""
    return name.strip().replace(" ", "_").replace("·", "_").replace(".", "")


def read_input_file(filepath: str) -> str:
    """입력 파일 전체를 읽는다."""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def chunk_text(text: str) -> list[str]:
    """긴 텍스트를 MAX_TEXT_LENGTH 단위로 분할한다.

    각 청크(chunk)는 CHUNK_OVERLAP만큼 겹쳐 엔티티/관계가 경계에서 잘리는 것을 방지한다.
    MAX_TEXT_LENGTH 이하인 텍스트는 단일 청크로 반환한다.
    """
    if len(text) <= MAX_TEXT_LENGTH:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + MAX_TEXT_LENGTH
        chunks.append(text[start:end])
        start = end - CHUNK_OVERLAP
    return chunks
