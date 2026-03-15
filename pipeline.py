#!/usr/bin/env python3
"""GraphRAG 파이프라인 오케스트레이터.

그래프 추출 이후 단계(커뮤니티 탐지 → 리포트 생성 → 보강 → 임베딩)를
순서대로 실행한다. 각 단계의 출력 파일이 이미 존재하면 건너뛴다.

Usage:
    python3 pipeline.py                    # 이어서 실행
    python3 pipeline.py --force            # 전체 재실행
    python3 pipeline.py --from 3           # 3단계부터 실행
    python3 pipeline.py --hierarchical     # 계층적 커뮤니티 포함
"""

import argparse
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _build_steps(hierarchical: bool) -> list[tuple]:
    """파이프라인 단계를 구성한다."""
    detect_cmd = [sys.executable, "scripts/detect_communities.py"]
    report_cmd = [sys.executable, "scripts/generate_community_reports.py"]
    if hierarchical:
        detect_cmd.append("--hierarchical")
        report_cmd.append("--hierarchical")

    return [
        (
            "의미 기반 중복 제거",
            [sys.executable, "scripts/deduplicate_semantic.py", "--no-llm", "--apply"],
            BASE_DIR / "data" / "output" / ".dedup_done",
        ),
        (
            "커뮤니티 탐지 (Leiden)",
            detect_cmd,
            BASE_DIR / "data" / "output" / "communities.json",
        ),
        (
            "커뮤니티 리포트 생성 (LLM)",
            report_cmd,
            BASE_DIR / "data" / "output" / "community_reports.json",
        ),
        (
            "데이터셋 보강",
            [sys.executable, "scripts/enrich_graph.py"],
            BASE_DIR / "frontend" / "src" / "data.json",
        ),
        (
            "노드 임베딩 생성",
            [sys.executable, "scripts/build_embeddings.py"],
            BASE_DIR / "data" / "output" / "embeddings.npz",
        ),
        (
            "Claim 추출 (LLM)",
            [sys.executable, "scripts/extract_claims.py"],
            BASE_DIR / "data" / "output" / "claims.json",
        ),
    ]


def run_pipeline(
    force: bool = False,
    from_step: int = 1,
    hierarchical: bool = False,
) -> None:
    """파이프라인을 실행한다."""
    steps = _build_steps(hierarchical)
    total = len(steps)
    mode = "계층적" if hierarchical else "단일 레벨"
    print(f"=== GraphRAG 파이프라인 시작 ({total}단계, {mode}) ===\n")

    # 선행 조건 확인
    graph_exists = (
        (BASE_DIR / "data" / "output" / "graph_advanced.json").exists()
        or (BASE_DIR / "data" / "output" / "graph.json").exists()
    )
    if not graph_exists:
        print("오류: data/output/graph.json이 없습니다.")
        print("  preprocess_graph.py를 먼저 실행하세요.")
        sys.exit(1)

    for i, (name, cmd, output) in enumerate(steps, start=1):
        if i < from_step:
            print(f"[{i}/{total}] {name} — 건너뜀 (--from {from_step})")
            continue

        if not force and output.exists():
            print(f"[{i}/{total}] {name} — 건너뜀 ({output.name} 존재)")
            continue

        print(f"[{i}/{total}] {name} — 실행 중...")
        result = subprocess.run(cmd, cwd=str(BASE_DIR))

        if result.returncode != 0:
            print(f"\n오류: {name} 단계 실패 (exit code {result.returncode})")
            print(f"  이 단계부터 재실행: python3 pipeline.py --from {i}")
            sys.exit(result.returncode)

        print(f"  완료: {output.name}\n")

    print("=== 파이프라인 완료 ===")
    print("  ./start.sh 로 서버를 시작하세요.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GraphRAG 파이프라인")
    parser.add_argument("--force", action="store_true", help="전체 재실행")
    parser.add_argument("--from", type=int, default=1, dest="from_step",
                        help="N단계부터 실행 (1~6)")
    parser.add_argument("--hierarchical", action="store_true",
                        help="계층적 커뮤니티 탐지 + 리포트 생성")
    args = parser.parse_args()
    run_pipeline(
        force=args.force,
        from_step=args.from_step,
        hierarchical=args.hierarchical,
    )
