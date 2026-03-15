#!/usr/bin/env python3
"""커뮤니티 리포트 생성(community report generation) 실행 스크립트.

Leiden 탐지 결과의 각 커뮤니티에 대해 LLM 기반 리포트를 생성하고 저장한다.
communities.json이 선행 필수 (scripts/detect_communities.py 실행 후).
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.community_report import generate_community_report
from core.graph_utils import load_graph

COMMUNITIES_PATH = BASE_DIR / "data" / "output" / "communities.json"
_GRAPH_ADVANCED = BASE_DIR / "data" / "output" / "graph_advanced.json"
_GRAPH_DEFAULT = BASE_DIR / "data" / "output" / "graph.json"
GRAPH_PATH = _GRAPH_ADVANCED if _GRAPH_ADVANCED.exists() else _GRAPH_DEFAULT
OUTPUT_PATH = BASE_DIR / "data" / "output" / "community_reports.json"

# 리포트 생성 대상에서 제외할 커뮤니티 (고립 노드)
SKIP_COMMUNITY_IDS = {"uncategorized"}


def run() -> None:
    """모든 커뮤니티의 리포트를 생성한다."""
    print("=== 커뮤니티 리포트 생성 시작 ===")

    if not COMMUNITIES_PATH.exists():
        print("오류: communities.json이 없습니다. detect_communities.py를 먼저 실행하세요.")
        sys.exit(1)

    with open(COMMUNITIES_PATH, encoding="utf-8") as f:
        comm_data = json.load(f)

    graph = load_graph(str(GRAPH_PATH))
    membership = comm_data["membership"]
    communities = comm_data["communities"]

    # 기존 리포트가 있으면 로드 (중단 후 재개 지원)
    existing_reports = {}
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            for report in json.load(f):
                existing_reports[report["community_id"]] = report
        print(f"기존 리포트 {len(existing_reports)}개 로드됨 (중단 재개 모드)")

    reports = []
    for comm in communities:
        comm_id = comm["id"]
        comm_idx = comm["index"]
        comm_name = comm["name"]

        if comm_id in SKIP_COMMUNITY_IDS:
            print(f"  [건너뜀] {comm_name} (고립 노드 그룹)")
            continue

        # 이미 리포트가 있으면 재사용
        if comm_id in existing_reports:
            print(f"  [캐시] {comm_name}: 기존 리포트 재사용")
            reports.append(existing_reports[comm_id])
            continue

        report = generate_community_report(
            graph, membership, comm_idx, comm_id,
        )
        report["community_name"] = comm_name
        reports.append(report)

        # 진행 중간 저장 (LLM 호출 실패 대비)
        _save_reports(reports)

    _save_reports(reports)
    print(f"\n=== 리포트 생성 완료: {len(reports)}개 ===")
    print(f"저장: {OUTPUT_PATH}")


def _save_reports(reports: list[dict]) -> None:
    """리포트를 JSON 파일로 저장한다."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)


def run_hierarchical() -> None:
    """계층적 커뮤니티의 모든 레벨 리포트를 생성한다.

    Level 1(기본) 리포트를 먼저 생성하고,
    Level 0(대분류)은 하위 리포트 요약을 입력으로 사용한다(bottom-up).
    Level 2(세분류)는 개별 노드/링크로 생성한다.
    """
    print("=== 계층적 커뮤니티 리포트 생성 시작 ===")

    if not COMMUNITIES_PATH.exists():
        print("오류: communities.json이 없습니다.")
        sys.exit(1)

    with open(COMMUNITIES_PATH, encoding="utf-8") as f:
        comm_data = json.load(f)

    levels = comm_data.get("levels")
    if not levels:
        print("계층 데이터 없음. 단일 레벨 리포트로 폴백합니다.")
        run()
        return

    graph = load_graph(str(GRAPH_PATH))
    all_reports: dict[int, list[dict]] = {}  # level → reports

    # 기존 리포트 캐시
    existing_reports = {}
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            for report in json.load(f):
                key = f"{report.get('level', 1)}_{report['community_id']}"
                existing_reports[key] = report

    # Level 1(기본)과 Level 2(세분류)를 먼저 생성 (bottom-up)
    for level_data in sorted(levels, key=lambda l: l["level"], reverse=True):
        level = level_data["level"]
        membership = level_data["membership"]
        communities = level_data["communities"]

        print(f"\n--- Level {level} 리포트 생성 ({len(communities)}개 커뮤니티) ---")
        level_reports = []

        for comm in communities:
            comm_id = comm["id"]
            if comm_id in SKIP_COMMUNITY_IDS:
                continue

            cache_key = f"{level}_{comm_id}"
            if cache_key in existing_reports:
                print(f"  [캐시] L{level} {comm['name']}")
                level_reports.append(existing_reports[cache_key])
                continue

            # Level 0: 하위 레벨 리포트 요약을 입력으로 사용
            if level == 0 and 1 in all_reports:
                report = _generate_summary_report(
                    comm, membership, all_reports[1], graph,
                )
            else:
                report = generate_community_report(
                    graph, membership, comm["index"], comm_id,
                )

            report["community_name"] = comm["name"]
            report["level"] = level
            level_reports.append(report)

            # 중간 저장
            _save_all_reports(all_reports, level_reports, level)

        all_reports[level] = level_reports

    # 전체 리포트를 하나의 파일에 저장 (기존 호환: Level 1이 기본)
    flat_reports = []
    for level in sorted(all_reports.keys()):
        flat_reports.extend(all_reports[level])

    _save_reports(flat_reports)
    for level, reports in sorted(all_reports.items()):
        print(f"  Level {level}: {len(reports)}개 리포트")
    print(f"\n=== 계층적 리포트 생성 완료: 총 {len(flat_reports)}개 ===")


def _generate_summary_report(
    comm: dict,
    membership: dict,
    child_reports: list[dict],
    graph: dict,
) -> dict:
    """하위 레벨 리포트를 요약하여 상위 레벨 리포트를 생성한다."""
    from core.claude_client import call_claude, parse_claude_response
    from core.community_report import load_prompt_template

    # 이 커뮤니티에 속한 노드들
    comm_node_ids = set(comm.get("node_ids", []))

    # 하위 리포트 중 이 커뮤니티 노드와 겹치는 것을 수집
    relevant_summaries = []
    for child in child_reports:
        child_comm_id = child.get("community_id", "")
        # 하위 리포트의 커뮤니티 노드와 겹침 확인
        child_title = child.get("title", child_comm_id)
        child_summary = child.get("summary", "")
        if child_summary:
            relevant_summaries.append(f"- {child_title}: {child_summary}")

    if not relevant_summaries:
        # 폴백: 일반 리포트 생성
        from core.community_report import generate_community_report
        return generate_community_report(graph, membership, comm["index"], comm["id"])

    # 하위 요약을 컨텍스트로 주입
    template = load_prompt_template()
    context = (
        f"이 커뮤니티는 {comm['node_count']}개 노드를 포함하는 대분류 그룹입니다.\n\n"
        f"하위 커뮤니티 요약:\n" + "\n".join(relevant_summaries[:10])
    )
    prompt = template.replace("{input_text}", context).replace(
        "{max_report_length}", "1500"
    )

    print(f"  [L0] {comm['name']}: 하위 {len(relevant_summaries)}개 요약 기반 생성...")
    raw = call_claude(prompt)
    report = parse_claude_response(raw)
    report["community_id"] = comm["id"]
    return report


def _save_all_reports(
    all_reports: dict,
    current_level_reports: list[dict],
    current_level: int,
) -> None:
    """현재까지의 모든 리포트를 중간 저장한다."""
    flat = []
    for level in sorted(all_reports.keys()):
        flat.extend(all_reports[level])
    flat.extend(current_level_reports)
    _save_reports(flat)


if __name__ == "__main__":
    if "--hierarchical" in sys.argv:
        run_hierarchical()
    else:
        run()
