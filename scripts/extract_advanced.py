"""고도화된 AI 기반 엔티티/관계 추출 파이프라인.

preprocess_graph.py의 후속 스크립트로, 3가지 핵심 알고리즘을 적용하여
data/output/graph.json의 품질을 향상시킨다.

핵심 알고리즘:
  1. 동명이인(homonym) 문맥 분석 — 활동 맥락 기반 ID 분리
  2. 중요 노드 보강(Importance Reinforcement) — 고립 노드 + 고중요도 저연결 노드 관계 재탐색
  3. 역사적 중요도 가중치 펌핑 — LLM 기반 동적 weight 산정

입력: data/input/*.txt, data/output/graph.json
출력: data/output/graph_advanced.json

주의: 이 스크립트는 claude CLI를 subprocess로 호출한다.
"""

import argparse
import os
import sys

# 프로젝트 루트를 sys.path에 추가하여 core 패키지 임포트 가능하게 함
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.algorithms import (
    run_homonym_analysis,
    run_importance_pumping,
    run_isolated_node_pass,
)
from core.graph_utils import find_isolated_nodes, load_graph, save_graph

INPUT_DIR = os.path.join(BASE_DIR, "data", "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output")
INPUT_GRAPH = os.path.join(OUTPUT_DIR, "graph.json")
OUTPUT_GRAPH = os.path.join(OUTPUT_DIR, "graph_advanced.json")


def main():
    """3가지 핵심 알고리즘을 순차 적용하는 메인 파이프라인."""
    parser = argparse.ArgumentParser(
        description="ManseiGraph 고도화 추출 파이프라인 (동명이인·고립노드·가중치)"
    )
    parser.add_argument(
        "--input", default=INPUT_GRAPH,
        help=f"입력 그래프 경로 (기본: {INPUT_GRAPH})",
    )
    parser.add_argument(
        "--output", default=OUTPUT_GRAPH,
        help=f"출력 그래프 경로 (기본: {OUTPUT_GRAPH})",
    )
    parser.add_argument(
        "--skip-homonym", action="store_true",
        help="알고리즘 1 (동명이인 분석) 건너뛰기",
    )
    parser.add_argument(
        "--skip-isolated", action="store_true",
        help="알고리즘 2 (고립 노드 재탐색) 건너뛰기",
    )
    parser.add_argument(
        "--skip-importance", action="store_true",
        help="알고리즘 3 (중요도 펌핑) 건너뛰기",
    )
    args = parser.parse_args()

    # 입력 그래프 로드
    if not os.path.exists(args.input):
        print(f"[오류] 입력 그래프를 찾을 수 없습니다: {args.input}")
        print("먼저 preprocess_graph.py를 실행하여 graph.json을 생성하세요.")
        sys.exit(1)

    print("═══ ManseiGraph 고도화 추출 파이프라인 ═══")
    graph = load_graph(args.input)
    print(f"입력 그래프: 노드 {len(graph['nodes'])}개, 링크 {len(graph['links'])}개")

    # 알고리즘 1: 동명이인 문맥 분석
    if not args.skip_homonym:
        graph = run_homonym_analysis(graph, INPUT_DIR)

    # 알고리즘 3→2 순서 변경: 중요도 펌핑을 먼저 실행해야 보강 대상을 정확히 식별 가능
    if not args.skip_importance:
        graph = run_importance_pumping(graph)

    # 알고리즘 2: 고립 노드 + 고중요도 저연결 노드 보강
    if not args.skip_isolated:
        graph = run_isolated_node_pass(graph, INPUT_DIR)

    # 최종 저장
    save_graph(
        {"nodes": graph["nodes"], "links": graph["links"]},
        args.output,
    )

    print(f"\n═══ 파이프라인 완료 ═══")
    print(f"출력: 노드 {len(graph['nodes'])}개, 링크 {len(graph['links'])}개")
    print(f"저장: {args.output}")

    # 통계 요약
    isolated_after = find_isolated_nodes(graph)
    persons = [n for n in graph["nodes"] if n.get("type") == "person"]
    high_importance = [n for n in persons if n.get("importance_weight", 0) >= 4]
    print(f"\n── 통계 ──")
    print(f"  인물 노드: {len(persons)}개")
    print(f"  고립 노드: {len(isolated_after)}개")
    print(f"  고중요도(≥4) 인물: {len(high_importance)}개")


if __name__ == "__main__":
    main()
