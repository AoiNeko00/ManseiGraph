"""core/text_utils.py 단위 테스트."""

from core.text_utils import chunk_text, normalize_id


def test_normalize_id_basic():
    """기본 ID 정규화 검증."""
    assert normalize_id("김 구") == "김_구"
    assert normalize_id("안·중·근") == "안_중_근"
    assert normalize_id("Mr. Kim") == "Mr_Kim"


def test_normalize_id_strip():
    """공백 제거 검증."""
    assert normalize_id("  김구  ") == "김구"


def test_chunk_text_short():
    """짧은 텍스트는 단일 청크 검증."""
    text = "짧은 텍스트"
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_long():
    """긴 텍스트 분할 + 겹침 검증."""
    # MAX_TEXT_LENGTH보다 긴 텍스트 생성
    from core.constants import CHUNK_OVERLAP, MAX_TEXT_LENGTH
    text = "가" * (MAX_TEXT_LENGTH + 1000)
    chunks = chunk_text(text)

    assert len(chunks) >= 2
    # 첫 청크 길이
    assert len(chunks[0]) == MAX_TEXT_LENGTH
    # 겹침 부분이 존재해야 함
    overlap = chunks[0][-CHUNK_OVERLAP:]
    assert chunks[1][:CHUNK_OVERLAP] == overlap
