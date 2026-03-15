"""data/input/*.txt에서 엔티티와 관계를 추출하여 react-force-graph용 JSON을 생성하는 스크립트.

내부적으로 'claude --print --model sonnet --output-format json' 명령어를 subprocess로 호출하여 텍스트를 분석한다.
결과물은 data/output/graph.json에 저장된다.

고도화 기능:
  - 동명이인(homonym) 자동 분리: 문맥 내 활동 시기/역할 분석
  - Multi-pass 관계 재탐색: 1차 노드 리스트 기반 2차 Cross-check
  - 역사적 중요도 보정: 직책/상징성 기반 degree 가중치

출력 구조:
  nodes: [{id, name, type, description, degree, importance_weight}, ...]
  links: [{source, target, weight, strength, relation, description}, ...]
"""

import argparse
import glob
import json
import os
import sys
import time

from core.claude_client import call_claude, parse_claude_response
from core.constants import SYMBOLIC_WEIGHTS
from core.graph_merge import format_node_list, merge_results, resolve_homonyms
from core.prompts import CROSSCHECK_PROMPT, EXTRACTION_PROMPT
from core.text_utils import chunk_text, normalize_id, read_input_file

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "data", "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "graph.json")


# === Pass 1: 기본 엔티티/관계 추출 ===
def extract_from_file(filepath: str) -> dict:
    """단일 파일에서 엔티티와 관계를 추출한다 (1차 추출).

    MAX_TEXT_LENGTH 초과 시 청킹하여 각 청크별 추출 후 병합한다.
    """
    text = read_input_file(filepath)
    filename = os.path.basename(filepath)
    chunks = chunk_text(text)
    print(f"  [Pass 1] {filename} ({len(text):,}자, {len(chunks)}청크)")

    all_entities = []
    all_relationships = []
    for ci, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"    청크 {ci + 1}/{len(chunks)} ({len(chunk):,}자)")
        prompt = EXTRACTION_PROMPT.format(text=chunk)
        raw_response = call_claude(prompt)
        result = parse_claude_response(raw_response)
        all_entities.extend(result.get("entities", []))
        all_relationships.extend(result.get("relationships", []))
        if ci < len(chunks) - 1:
            time.sleep(1)

    return {"entities": all_entities, "relationships": all_relationships}


# === Pass 2: Cross-check로 누락 관계 재탐색 ===
def crosscheck_from_file(filepath: str, node_list_str: str) -> dict:
    """단일 파일에서 누락된 관계를 2차로 탐색한다.

    MAX_TEXT_LENGTH 초과 시 청킹하여 각 청크별 탐색 후 병합한다.
    """
    text = read_input_file(filepath)
    filename = os.path.basename(filepath)
    chunks = chunk_text(text)
    print(f"  [Pass 2] {filename} ({len(chunks)}청크)")

    all_entities = []
    all_relationships = []
    for ci, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"    청크 {ci + 1}/{len(chunks)} ({len(chunk):,}자)")
        prompt = CROSSCHECK_PROMPT.format(node_list=node_list_str, text=chunk)
        raw_response = call_claude(prompt)
        result = parse_claude_response(raw_response)
        all_entities.extend(result.get("entities", []))
        all_relationships.extend(result.get("relationships", []))
        if ci < len(chunks) - 1:
            time.sleep(1)

    return {"entities": all_entities, "relationships": all_relationships}


def main():
    """메인 실행 함수."""
    parser = argparse.ArgumentParser(description="ManseiGraph 전처리 (고도화)")
    parser.add_argument("--limit", type=int, default=0,
                        help="처리할 파일 수 제한 (0=전체)")
    parser.add_argument("--files", nargs="+", default=[],
                        help="처리할 특정 파일명 목록 (예: 김구.txt 안창호.txt)")
    parser.add_argument("--skip-pass2", action="store_true",
                        help="2차 Cross-check 패스를 건너뛴다")
    args = parser.parse_args()

    if args.files:
        input_files = []
        for fname in args.files:
            fpath = os.path.join(INPUT_DIR, fname)
            if os.path.exists(fpath):
                input_files.append(fpath)
            else:
                print(f"[경고] 파일을 찾을 수 없습니다: {fpath}")
        input_files = sorted(input_files)
    else:
        input_files = sorted(glob.glob(os.path.join(INPUT_DIR, "*.txt")))

    if not input_files:
        print("[오류] 처리할 .txt 파일이 없습니다.")
        sys.exit(1)

    if args.limit > 0:
        input_files = input_files[:args.limit]

    print("=== ManseiGraph 전처리 시작 (고도화 버전) ===")
    print(f"입력 파일: {len(input_files)}개")
    print()

    # ─── Pass 1: 기본 추출 ───
    print("── Pass 1: 엔티티/관계 기본 추출 ──")
    all_results = []
    failed = []

    for i, filepath in enumerate(input_files, 1):
        filename = os.path.basename(filepath)
        print(f"[{i}/{len(input_files)}] {filename}")

        try:
            result = extract_from_file(filepath)
            entities_count = len(result.get("entities", []))
            rels_count = len(result.get("relationships", []))
            print(f"  [완료] 엔티티 {entities_count}개, 관계 {rels_count}개")
            all_results.append(result)
        except Exception as e:
            print(f"  [실패] {e}")
            failed.append(filename)

        if i < len(input_files):
            time.sleep(1)

    print("\n=== Pass 1 결과 병합 중 ===")
    graph = merge_results(all_results)

    # ─── 동명이인 감지 ───
    print("\n── 동명이인 감지 ──")
    graph = resolve_homonyms(graph)

    # ─── Pass 2: Cross-check 누락 관계 재탐색 ───
    if not args.skip_pass2:
        print("\n── Pass 2: Cross-check 누락 관계 재탐색 ──")
        nodes_map = {n["id"]: n for n in graph["nodes"]}
        node_list_str = format_node_list(nodes_map)

        pass2_results = []
        for i, filepath in enumerate(input_files, 1):
            filename = os.path.basename(filepath)
            print(f"[{i}/{len(input_files)}] {filename}")

            try:
                result = crosscheck_from_file(filepath, node_list_str)
                new_rels = len(result.get("relationships", []))
                new_ents = len(result.get("entities", []))
                if new_rels > 0 or new_ents > 0:
                    print(f"  [발견] 새 엔티티 {new_ents}개, 새 관계 {new_rels}개")
                    pass2_results.append(result)
                else:
                    print(f"  [추가 없음]")
            except Exception as e:
                print(f"  [실패] {e}")

            if i < len(input_files):
                time.sleep(1)

        # Pass 2 결과를 기존 그래프에 병합
        if pass2_results:
            print(f"\n=== Pass 2 결과 병합 ({len(pass2_results)}개 파일에서 추가 발견) ===")
            existing_nodes = {n["id"]: n for n in graph["nodes"]}
            existing_links = {
                (l["source"], l["target"], l["relation"])
                for l in graph["links"]
            }

            new_link_count = 0
            new_node_count = 0

            for result in pass2_results:
                # 새 엔티티 추가
                for entity in result.get("entities", []):
                    eid = normalize_id(entity.get("id", entity["name"]))
                    if eid not in existing_nodes:
                        node = {
                            "id": eid,
                            "name": entity["name"],
                            "type": entity.get("type", "concept"),
                            "description": entity.get("description", ""),
                            "degree": 0,
                            "importance_weight": 0,
                        }
                        # 이름 기반 가중치 적용
                        name = entity["name"]
                        if name in SYMBOLIC_WEIGHTS:
                            node["importance_weight"] = SYMBOLIC_WEIGHTS[name]
                            node["degree"] += SYMBOLIC_WEIGHTS[name] * 3
                        existing_nodes[eid] = node
                        new_node_count += 1

                # 새 관계 추가
                for rel in result.get("relationships", []):
                    source = normalize_id(rel["source"])
                    target = normalize_id(rel["target"])
                    relation = rel.get("type", "related_to")
                    link_key = (source, target, relation)

                    if link_key not in existing_links:
                        if source in existing_nodes and target in existing_nodes:
                            graph["links"].append({
                                "source": source,
                                "target": target,
                                "weight": 1,
                                "strength": rel.get("strength", 5),
                                "relation": relation,
                                "description": rel.get("description", ""),
                            })
                            existing_links.add(link_key)
                            existing_nodes[source]["degree"] += 1
                            existing_nodes[target]["degree"] += 1
                            new_link_count += 1

            graph["nodes"] = list(existing_nodes.values())
            print(f"  새 노드: {new_node_count}개, 새 링크: {new_link_count}개 추가됨")

    # 출력 디렉토리 생성 및 저장
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"nodes": graph["nodes"], "links": graph["links"]},
            f, ensure_ascii=False, indent=2,
        )

    print(f"\n=== 전처리 완료 ===")
    print(f"노드(nodes): {len(graph['nodes'])}개")
    print(f"링크(links): {len(graph['links'])}개")
    print(f"출력 파일: {OUTPUT_FILE}")
    if failed:
        print(f"실패 파일: {failed}")

    # 주요 인물 degree 요약
    print("\n── 주요 인물 degree 현황 ──")
    key_persons = ["김구", "이승만", "안창호", "김규식", "여운형", "함태영",
                   "안중근", "윤봉길", "김원봉", "홍범도", "손병희"]
    for node in sorted(graph["nodes"], key=lambda n: -n.get("degree", 0)):
        if node["name"] in key_persons or any(kp in node["name"] for kp in key_persons):
            print(f"  {node['name']}: degree={node['degree']} "
                  f"(가중치={node.get('importance_weight', 0)})")


if __name__ == "__main__":
    main()
