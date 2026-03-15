"""고도화 추출 알고리즘(algorithm) 모듈.

동명이인 문맥 분석, 중요 노드 보강, 역사적 중요도 가중치 펌핑
3가지 알고리즘의 실행 로직을 제공한다.
"""

import os
import time

from core.claude_client import call_claude, parse_claude_response
from core.constants import MAX_TEXT_LENGTH
from core.graph_utils import (
    add_relations_to_graph,
    build_node_index,
    compute_degree,
    find_isolated_nodes,
    find_relevant_files,
    find_underlinked_important_nodes,
    format_existing_nodes,
)
from core.prompts_advanced import (
    HOMONYM_ANALYSIS_PROMPT,
    IMPORTANCE_PUMPING_PROMPT,
    IMPORTANCE_REINFORCEMENT_PROMPT,
    ISOLATED_NODE_PROMPT,
)
from core.text_utils import normalize_id, read_input_file

# 동명이인 분석 시 사전 확인할 인물 목록
KNOWN_HOMONYM_NAMES = ["김규식", "이승만", "김성수", "이동녕", "이시영"]


# ──────────────────────────────────────────────
# 알고리즘 1: 동명이인 문맥 분석
# ──────────────────────────────────────────────
def run_homonym_analysis(graph: dict, input_dir: str) -> dict:
    """동명이인 후보를 찾아 LLM으로 문맥 분석한다.

    같은 이름(name)을 가진 노드가 여러 개이거나,
    description에서 활동 맥락이 모호한 노드를 대상으로 분석한다.
    """
    print("\n══ 알고리즘 1: 동명이인 문맥 분석 ══")

    # 이름별 노드 그룹핑
    name_groups: dict[str, list[dict]] = {}
    for node in graph["nodes"]:
        if node["type"] != "person":
            continue
        base_name = node["name"].split("(")[0].strip()  # "김규식 (외교)" → "김규식"
        if base_name not in name_groups:
            name_groups[base_name] = []
        name_groups[base_name].append(node)

    # 잠재적 동명이인: 같은 이름에 2개 이상 노드가 있는 경우
    homonym_candidates = {
        name: nodes for name, nodes in name_groups.items()
        if len(nodes) >= 2
    }

    # 단일 노드이지만 사전 목록에 있는 인물 추가
    for name in KNOWN_HOMONYM_NAMES:
        if name in name_groups and name not in homonym_candidates:
            homonym_candidates[name] = name_groups[name]

    if not homonym_candidates:
        print("  동명이인 후보 없음")
        return graph

    print(f"  동명이인 후보: {len(homonym_candidates)}명")
    changes_made = 0

    for name, nodes in homonym_candidates.items():
        current_info = "\n".join(
            f"- ID: {n['id']}, 설명: {n['description']}"
            for n in nodes
        )

        # 관련 텍스트 수집
        relevant_files = find_relevant_files(name, input_dir)
        if not relevant_files:
            print(f"  [{name}] 관련 파일 없음, 건너뜀")
            continue

        # 가장 관련성 높은 파일의 텍스트 사용
        text = read_input_file(relevant_files[0])

        prompt = HOMONYM_ANALYSIS_PROMPT.format(
            name=name,
            current_info=current_info,
            text=text,
        )

        print(f"  [{name}] 분석 중...")
        try:
            result = parse_claude_response(call_claude(prompt))
        except Exception as e:
            print(f"  [{name}] 분석 실패: {e}")
            continue

        if result.get("is_homonym"):
            persons = result.get("persons", [])
            print(f"  [{name}] → 동명이인 확인: {len(persons)}명으로 분리")

            # 기존 노드를 제거(remove)하고 분리된 노드로 교체
            old_ids = [n["id"] for n in nodes]
            graph["nodes"] = [n for n in graph["nodes"] if n["id"] not in old_ids]

            for p in persons:
                new_id = normalize_id(p["id"])
                new_node = {
                    "id": new_id,
                    "name": p.get("name", name),
                    "type": "person",
                    "description": p.get("description", ""),
                    "degree": 0,
                    "importance_weight": 0,
                }
                graph["nodes"].append(new_node)

                # 기존 링크에서 old_id → new_id 매핑 (맥락에 맞는 쪽으로)
                for link in graph["links"]:
                    for old_id in old_ids:
                        if link["source"] == old_id:
                            link["source"] = new_id
                        if link["target"] == old_id:
                            link["target"] = new_id

            changes_made += 1
        else:
            print(f"  [{name}] → 동일 인물 확인: {result.get('analysis', '')[:60]}")

        time.sleep(1)

    print(f"  동명이인 분리 완료: {changes_made}건 변경")
    return graph


# ──────────────────────────────────────────────
# 알고리즘 2: 중요 노드 보강 패스 (Importance Reinforcement Pass)
# ──────────────────────────────────────────────
def run_isolated_node_pass(graph: dict, input_dir: str) -> dict:
    """중요 노드 보강 패스: 고립 노드 + 고중요도 저연결 노드의 관계를 재탐색한다.

    Phase A: degree=0인 고립 노드 → ISOLATED_NODE_PROMPT로 관계 복구
    Phase B: importance >= 4이면서 link < 10인 노드 → IMPORTANCE_REINFORCEMENT_PROMPT로 보강
    """
    print("\n══ 알고리즘 2: 중요 노드 보강 패스 (Importance Reinforcement) ══")

    # degree 재계산
    compute_degree(graph)

    node_index = build_node_index(graph)
    existing_links = {
        (l["source"], l["target"], l["relation"])
        for l in graph["links"]
    }
    existing_nodes_str = format_existing_nodes(graph)

    new_links_total = 0
    new_nodes_total = 0

    # ── Phase A: 고립 노드(degree=0) 관계 재탐색 ──
    isolated = find_isolated_nodes(graph)
    if isolated:
        print(f"\n  ── Phase A: 고립 노드 {len(isolated)}개 ──")
        for node in isolated:
            print(f"    - {node['name']} ({node['id']})")

        for node in isolated:
            relevant_files = find_relevant_files(node["name"], input_dir)
            if not relevant_files:
                print(f"  [{node['name']}] 관련 파일 없음, 건너뜀")
                continue

            combined_text = ""
            for fpath in relevant_files[:3]:
                text = read_input_file(fpath)
                fname = os.path.basename(fpath)
                combined_text += f"\n\n--- [{fname}] ---\n{text}"
                if len(combined_text) > MAX_TEXT_LENGTH:
                    combined_text = combined_text[:MAX_TEXT_LENGTH]
                    break

            prompt = ISOLATED_NODE_PROMPT.format(
                node_name=node["name"],
                node_id=node["id"],
                node_description=node.get("description", ""),
                node_type=node.get("type", "person"),
                existing_nodes=existing_nodes_str,
                text=combined_text,
            )

            print(f"  [{node['name']}] 관계 재탐색 중 ({len(relevant_files)}개 파일)...")
            try:
                result = parse_claude_response(call_claude(prompt))
            except Exception as e:
                print(f"  [{node['name']}] 재탐색 실패: {e}")
                continue

            nl, nn = add_relations_to_graph(graph, result, node_index, existing_links)
            new_links_total += nl
            new_nodes_total += nn

            found = len(result.get("found_relations", []))
            print(f"  [{node['name']}] → {found}개 관계 발견 ({nl}개 신규 추가)")
            time.sleep(1)
    else:
        print("  Phase A: 고립 노드 없음")

    # degree 재계산 (Phase A 결과 반영)
    compute_degree(graph)

    # ── Phase B: 고중요도 저연결 노드 보강 ──
    underlinked = find_underlinked_important_nodes(graph)
    if underlinked:
        print(f"\n  ── Phase B: 고중요도 저연결 노드 {len(underlinked)}개 ──")
        for node in underlinked:
            print(f"    - {node['name']} (importance={node.get('_effective_importance', '?')}, "
                  f"links={node.get('_actual_links', '?')})")

        for node in underlinked:
            relevant_files = find_relevant_files(node["name"], input_dir)

            # 여러 파일에서 텍스트 결합 (최대 5개 파일로 확장)
            combined_text = ""
            for fpath in relevant_files[:5]:
                text = read_input_file(fpath)
                fname = os.path.basename(fpath)
                combined_text += f"\n\n--- [{fname}] ---\n{text}"
                if len(combined_text) > MAX_TEXT_LENGTH:
                    combined_text = combined_text[:MAX_TEXT_LENGTH]
                    break

            if not combined_text:
                combined_text = "(관련 텍스트 없음 — 역사 지식만으로 관계를 추출하라)"

            prompt = IMPORTANCE_REINFORCEMENT_PROMPT.format(
                node_name=node["name"],
                node_id=node["id"],
                node_description=node.get("description", ""),
                link_count=node.get("_actual_links", 0),
                importance=node.get("_effective_importance", 4),
                existing_nodes=existing_nodes_str,
                text=combined_text,
            )

            print(f"  [{node['name']}] 중요 노드 보강 중...")
            try:
                result = parse_claude_response(call_claude(prompt, timeout=240))
            except Exception as e:
                print(f"  [{node['name']}] 보강 실패: {e}")
                continue

            nl, nn = add_relations_to_graph(graph, result, node_index, existing_links)
            new_links_total += nl
            new_nodes_total += nn

            found = len(result.get("found_relations", []))
            print(f"  [{node['name']}] → {found}개 관계 발견 ({nl}개 신규 추가)")
            time.sleep(1)
    else:
        print("  Phase B: 보강 대상 없음")

    # 최종 degree 재계산
    compute_degree(graph)

    print(f"\n  보강 완료: 새 링크 {new_links_total}개, 새 노드 {new_nodes_total}개 추가")

    # 여전히 고립된 노드 보고
    still_isolated = find_isolated_nodes(graph)
    if still_isolated:
        print(f"  ※ 여전히 고립된 노드 {len(still_isolated)}개:")
        for n in still_isolated:
            print(f"    - {n['name']}")

    return graph


# ──────────────────────────────────────────────
# 알고리즘 3: 역사적 중요도 가중치 펌핑
# ──────────────────────────────────────────────
def run_importance_pumping(graph: dict) -> dict:
    """LLM을 활용하여 인물의 역사적 중요도를 동적으로 평가하고 weight를 펌핑한다.

    기존 preprocess_graph.py의 정적 SYMBOLIC_WEIGHTS 대신,
    LLM이 인물의 설명과 맥락을 분석하여 중요도를 산정한다.
    """
    print("\n══ 알고리즘 3: 역사적 중요도 가중치 펌핑 ══")

    person_nodes = [n for n in graph["nodes"] if n.get("type") == "person"]
    if not person_nodes:
        print("  person 타입 노드 없음")
        return graph

    # 배치(batch) 처리 — 한 번에 최대 20명씩 평가
    BATCH_SIZE = 20
    all_assessments = []

    for batch_start in range(0, len(person_nodes), BATCH_SIZE):
        batch = person_nodes[batch_start:batch_start + BATCH_SIZE]
        node_list_str = "\n".join(
            f"- ID: {n['id']}, 이름: {n['name']}, 설명: {n.get('description', '(없음)')}, "
            f"현재 degree: {n.get('degree', 0)}"
            for n in batch
        )

        prompt = IMPORTANCE_PUMPING_PROMPT.format(node_list=node_list_str)
        batch_label = f"{batch_start + 1}~{min(batch_start + BATCH_SIZE, len(person_nodes))}"
        print(f"  [{batch_label}/{len(person_nodes)}] 중요도 평가 중...")

        try:
            result = parse_claude_response(call_claude(prompt))
            assessments = result.get("assessments", [])
            all_assessments.extend(assessments)
            print(f"  [{batch_label}] → {len(assessments)}명 평가 완료")
        except Exception as e:
            print(f"  [{batch_label}] 평가 실패: {e}")

        time.sleep(1)

    # 평가 결과를 그래프에 반영
    node_index = build_node_index(graph)
    pumped_count = 0

    for assessment in all_assessments:
        nid = normalize_id(assessment.get("id", ""))
        if nid not in node_index:
            # ID가 정확히 매칭되지 않으면 이름으로 탐색
            target_name = assessment.get("name", "")
            matched = [n for n in graph["nodes"] if n["name"] == target_name]
            if matched:
                nid = matched[0]["id"]
            else:
                continue

        score = assessment.get("importance_score", 1)
        score = max(1, min(5, score))  # 1~5 범위로 클램핑(clamping)

        # title_boost, symbolic_boost가 true이면 추가 가중
        if assessment.get("title_boost"):
            score = min(5, score + 1)
        if assessment.get("symbolic_boost"):
            score = min(5, score + 1)

        node = node_index[nid]
        old_weight = node.get("importance_weight", 0)

        # 기존 weight와 LLM 평가 중 높은 쪽 채택
        new_weight = max(old_weight, score)
        node["importance_weight"] = new_weight

        # degree에 가중치 반영: importance_weight * 3을 degree에 가산
        # 기존 가중치 기반 degree 보정 제거 후 재적용
        base_degree = node.get("degree", 0)
        if old_weight > 0:
            base_degree -= old_weight * 3
        node["degree"] = max(0, base_degree) + new_weight * 3

        if new_weight != old_weight:
            pumped_count += 1
            print(f"    {node['name']}: {old_weight} → {new_weight} "
                  f"({assessment.get('reasoning', '')[:40]})")

    print(f"  가중치 펌핑 완료: {pumped_count}명 업데이트")
    return graph
