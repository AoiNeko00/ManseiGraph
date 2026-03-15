"""위키피디아에서 독립운동가/단체 본문을 수집하여 data/input/*.txt로 저장하는 스크립트."""

import os
import wikipediaapi

# 한국어 위키피디아 클라이언트 초기화
wiki = wikipediaapi.Wikipedia(
    user_agent="ManseiGraph/1.0 (https://github.com/manseigraph; contact@example.com)",
    language="ko",
)

# 수집 대상: 주요 독립운동가 및 단체/사건
TARGETS = [
    # 인물(Person)
    "안창호",
    "김구",
    "윤봉길",
    "안중근",
    "이봉창",
    "유관순",
    "신채호",
    "이승만",
    "여운형",
    "김원봉",
    "지청천",
    "홍범도",
    "이회영",
    "김좌진",
    "손병희",
    "한용운",
    "이광수",
    "박은식",
    "김규식",
    "조소앙",
    "이동휘",
    "이시영",
    "서재필",
    "윤치호",
    "나석주",
    "강우규",
    "이육사",
    "윤동주",
    "주시경",
    "남자현",
    # 단체/기관(Organization)
    "대한민국 임시정부",
    "신민회",
    "의열단",
    "한인애국단",
    "독립협회",
    "대한광복군",
    "조선의용대",
    "신간회",
    "대한독립군",
    "근우회",
    # 사건(Event)
    "3·1 운동",
    "6·10 만세운동",
    "광주학생항일운동",
    "봉오동 전투",
    "청산리 전투",
    "간도 참변",
    "을사조약",
    "경술국치",
    "의병",
    "동학 농민 운동",
]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "input")


def collect():
    """위키피디아 본문을 수집하여 파일로 저장."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    success = []
    failed = []

    for title in TARGETS:
        page = wiki.page(title)
        if not page.exists():
            print(f"[SKIP] '{title}' - 문서 없음")
            failed.append(title)
            continue

        # 파일명: 공백/특수문자를 언더스코어로 변환
        safe_name = title.replace(" ", "_").replace("·", "_").replace(".", "")
        filepath = os.path.join(OUTPUT_DIR, f"{safe_name}.txt")

        text = page.text
        if not text.strip():
            print(f"[SKIP] '{title}' - 본문 비어 있음")
            failed.append(title)
            continue

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)

        char_count = len(text)
        print(f"[OK]   '{title}' -> {safe_name}.txt ({char_count:,}자)")
        success.append(title)

    print(f"\n=== 수집 완료: 성공 {len(success)}건, 실패 {len(failed)}건 ===")
    if failed:
        print(f"실패 목록: {failed}")


if __name__ == "__main__":
    collect()
