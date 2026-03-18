"""검색 엔진(search engine) 모듈.

Local Search, Global Search(Map-Reduce), DRIFT Search를 실행한다.
"""

import json
from pathlib import Path

from core.claude_client import call_claude, parse_claude_response
from core.context_builder import (
    build_global_context,
    build_local_context,
    find_relevant_entities,
    format_global_context_chunk,
)
from core.graph_utils import build_node_index

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    """프롬프트 파일을 로드한다."""
    with open(PROMPTS_DIR / filename, encoding="utf-8") as f:
        return f.read()


def _extract_mentioned_nodes(
    answer: str,
    graph: dict,
) -> list[str]:
    """답변 텍스트에서 실제 언급된 노드 ID를 추출한다.

    두 가지 방식을 결합한다:
    1. 노드 이름/이명의 텍스트 매칭
    2. [Data: Entities (id); Relationships (id)] Citation 패턴 파싱
    """
    if not answer:
        return []

    mentioned_set: set[str] = set()

    # 방법 1: 이름 매칭
    for node in graph["nodes"]:
        name = node.get("name", "")
        if not name or len(name) < 2:
            continue

        base_name = name.split("(")[0].strip()
        if base_name and base_name in answer:
            mentioned_set.add(node["id"])
            continue

        if "(" in name:
            alias = name.split("(")[1].rstrip(")")
            if alias and len(alias) >= 2 and alias in answer:
                mentioned_set.add(node["id"])

    # 방법 2: Citation 패턴 파싱 — [Data: Entities (id, id); Relationships (id)]
    citation_nodes = _parse_citations(answer, graph)
    mentioned_set.update(citation_nodes)

    return list(mentioned_set)


def _parse_citations(answer: str, graph: dict) -> set[str]:
    """답변의 [Data: ...] Citation에서 엔티티/관계 ID를 추출하여 노드 ID로 변환한다."""
    import re

    result: set[str] = set()
    node_index = build_node_index(graph)

    # [Data: Entities (5, 7, 12); Relationships (23, 45)] 패턴
    citation_pattern = re.compile(r'\[Data:\s*([^\]]+)\]')
    entity_id_pattern = re.compile(r'Entities?\s*\(([^)]+)\)')
    rel_id_pattern = re.compile(r'Relationships?\s*\(([^)]+)\)')

    for citation_match in citation_pattern.finditer(answer):
        citation_text = citation_match.group(1)

        # Entity ID 추출
        for ent_match in entity_id_pattern.finditer(citation_text):
            ids_str = ent_match.group(1)
            for id_part in ids_str.split(","):
                id_part = id_part.strip().replace("+more", "")
                if not id_part:
                    continue
                # 숫자 ID → 인덱스로 노드 찾기
                try:
                    idx = int(id_part)
                    if 0 <= idx < len(graph["nodes"]):
                        result.add(graph["nodes"][idx]["id"])
                except ValueError:
                    # 문자열 ID → 직접 매칭
                    if id_part in node_index:
                        result.add(id_part)

        # Relationship ID → source/target 노드 추출
        for rel_match in rel_id_pattern.finditer(citation_text):
            ids_str = rel_match.group(1)
            for id_part in ids_str.split(","):
                id_part = id_part.strip().replace("+more", "")
                try:
                    idx = int(id_part)
                    if 0 <= idx < len(graph["links"]):
                        link = graph["links"][idx]
                        src = link["source"] if isinstance(link["source"], str) else link["source"].get("id", "")
                        tgt = link["target"] if isinstance(link["target"], str) else link["target"].get("id", "")
                        if src in node_index:
                            result.add(src)
                        if tgt in node_index:
                            result.add(tgt)
                except ValueError:
                    pass

    return result


def _select_hierarchy_level(query: str, graph: dict) -> int | None:
    """질의 범위를 분석하여 적절한 커뮤니티 계층 레벨을 선택한다.

    키워드 매칭으로 이름이 직접 언급된 엔티티 수를 세어 질의의 폭을 판단한다.
    - 1~2개 직접 언급: 좁은 질의 → Level 2 (세분류)
    - 3~5개 직접 언급: 중간 질의 → Level 1 (기본)
    - 0개 또는 5개 초과: 넓은 질의 → Level 0 (대분류)

    계층 데이터가 없으면 None을 반환하여 전체 리포트를 사용한다.
    """
    from pathlib import Path
    import json

    communities_path = Path(__file__).resolve().parent.parent / "data" / "output" / "communities.json"
    if not communities_path.exists():
        return None
    with open(communities_path, encoding="utf-8") as f:
        comm_data = json.load(f)
    if "levels" not in comm_data:
        return None

    # 이름 직접 매칭만 사용 (임베딩 유사도 제외)
    # concept 타입은 추상적이므로 범위 판단에서 제외 (인물, 단체, 사건, 장소만)
    query_lower = query.lower()
    direct_matches = 0
    for node in graph["nodes"]:
        if node.get("type") == "concept":
            continue
        name = node.get("name", "")
        if not name or len(name) < 2:
            continue
        base_name = name.split("(")[0].strip()
        if base_name and base_name in query_lower:
            direct_matches += 1

    if 1 <= direct_matches <= 2:
        return 2  # 좁은 질의 → 세분류
    elif 3 <= direct_matches <= 5:
        return 1  # 중간 질의 → 기본
    else:
        return 0  # 넓은 질의 → 대분류


def local_search(
    query: str,
    graph: dict,
    response_type: str = "한국어로 상세하게 답변하라. 마크다운 형식으로 작성하라.",
) -> dict:
    """Local Search를 실행한다.

    관련 엔티티와 그 연결 관계를 기반으로 답변을 생성한다.

    Args:
        query: 사용자 질의.
        graph: 그래프 데이터.
        response_type: 응답 형식 지시.

    Returns:
        {"answer": str, "activated_nodes": list[str],
         "activated_communities": list[str]}
    """
    context_data = build_local_context(query, graph)
    if not context_data:
        return {
            "answer": "관련된 엔티티를 찾을 수 없습니다.",
            "activated_nodes": [],
            "activated_communities": [],
        }

    template = _load_prompt("local_search_system_prompt.txt")
    prompt = template.replace("{context_data}", context_data).replace(
        "{response_type}", response_type
    )
    prompt += f"\n\n---User Question---\n{query}"

    raw = call_claude(prompt)
    answer = _extract_text_response(raw)

    # 답변 텍스트에서 실제 언급된 노드를 추출
    activated_nodes = _extract_mentioned_nodes(answer, graph)

    node_index = build_node_index(graph)
    activated_communities = list({
        node_index[nid].get("communityId")
        for nid in activated_nodes
        if nid in node_index and node_index[nid].get("communityId")
    })

    return {
        "answer": answer,
        "activated_nodes": activated_nodes,
        "activated_communities": activated_communities,
    }


def global_search(
    query: str,
    graph: dict | None = None,
    response_type: str = "한국어로 상세하게 답변하라. 마크다운 형식으로 작성하라.",
    max_length: int = 2000,
    chunk_size: int = 5,
) -> dict:
    """Global Search (Map-Reduce)를 실행한다.

    모든 커뮤니티 리포트를 청크로 나누어 Map 단계를 실행하고,
    Reduce 단계에서 통합 답변을 생성한다.

    Args:
        query: 사용자 질의.
        response_type: 응답 형식 지시.
        max_length: 최대 응답 길이(단어).
        chunk_size: Map 단계당 처리할 리포트 수.

    Returns:
        {"answer": str, "activated_communities": list[str]}
    """
    # 질의 범위에 따라 계층 레벨 자동 선택
    level = _select_hierarchy_level(query, graph) if graph else None
    reports = build_global_context(level=level)
    if not reports:
        # 선택 레벨에 리포트가 없으면 전체로 폴백
        reports = build_global_context()
    if not reports:
        return {
            "answer": "커뮤니티 리포트가 없습니다. generate_community_reports.py를 먼저 실행하세요.",
            "activated_nodes": [],
            "activated_communities": [],
        }

    # 임베딩 기반 리포트 랭킹 (관련도 높은 리포트 우선)
    try:
        from core.embedding import rank_reports_by_query
        ranked = rank_reports_by_query(query, reports, top_k=max(len(reports), 10))
        if ranked:
            reports = ranked
    except ImportError:
        pass  # 임베딩 미설치 시 전체 리포트 사용

    # Map 단계: 각 청크에서 핵심 포인트 추출
    map_template = _load_prompt("global_search_map_system_prompt.txt")
    all_points = []

    for i in range(0, len(reports), chunk_size):
        chunk = reports[i:i + chunk_size]
        context = format_global_context_chunk(chunk)
        map_prompt = map_template.replace("{context_data}", context).replace(
            "{max_length}", str(max_length)
        )
        map_prompt += f"\n\n---User Question---\n{query}"

        print(f"  Map 단계 {i // chunk_size + 1}: 리포트 {i}~{i + len(chunk) - 1}")
        raw = call_claude(map_prompt)

        try:
            result = parse_claude_response(raw)
            points = result.get("points", [])
            all_points.extend(points)
        except (ValueError, json.JSONDecodeError):
            # JSON 파싱 실패 시 텍스트로 처리
            all_points.append({
                "description": _extract_text_response(raw),
                "score": 50,
            })

    # 중요도 순 정렬 후 상위 포인트만 Reduce에 전달
    all_points.sort(key=lambda p: -p.get("score", 0))
    top_points = all_points[:20]

    # Reduce 단계: 포인트 통합 → 최종 답변
    reduce_template = _load_prompt("global_search_reduce_system_prompt.txt")
    report_data = "\n\n".join(
        f"--- Analyst {i + 1} ---\n{p['description']}" for i, p in enumerate(top_points)
    )
    reduce_prompt = reduce_template.replace("{report_data}", report_data).replace(
        "{response_type}", response_type
    ).replace("{max_length}", str(max_length))
    reduce_prompt += f"\n\n---User Question---\n{query}"

    print("  Reduce 단계: 통합 답변 생성...")
    raw = call_claude(reduce_prompt)
    answer = _extract_text_response(raw)

    # 답변 텍스트에서 실제 언급된 노드를 추출
    activated_nodes = _extract_mentioned_nodes(answer, graph) if graph else []

    node_index = build_node_index(graph) if graph else {}
    activated_communities = list({
        node_index[nid].get("communityId")
        for nid in activated_nodes
        if nid in node_index and node_index[nid].get("communityId")
    })

    return {
        "answer": answer,
        "activated_nodes": activated_nodes,
        "activated_communities": activated_communities,
    }


def drift_search(
    query: str,
    graph: dict,
    response_type: str = "한국어로 상세하게 답변하라. 마크다운 형식으로 작성하라.",
    max_rounds: int = 2,
    num_followups: int = 2,
) -> dict:
    """DRIFT Search를 실행한다.

    Local 컨텍스트에서 시작하여 후속 질문으로 점진적으로 탐색을 확장한다.
    1) 초기 로컬 검색 → 부분 답변 + 후속 질문 생성
    2) 후속 질문으로 추가 컨텍스트 수집 (반복)
    3) 모든 부분 답변을 Reduce하여 최종 답변 생성

    Args:
        query: 사용자 질의.
        graph: 그래프 데이터.
        response_type: 응답 형식 지시.
        max_rounds: 최대 탐색 라운드 수.
        num_followups: 라운드당 후속 질문 수.

    Returns:
        {"answer": str, "activated_nodes": list, "activated_communities": list,
         "rounds": list[dict]}
    """
    drift_template = _load_prompt("drift_search_system_prompt.txt")
    reduce_template = _load_prompt("drift_reduce_prompt.txt")
    node_index = build_node_index(graph)

    all_activated_nodes: set[str] = set()
    round_results: list[dict] = []
    pending_queries = [query]

    for round_idx in range(max_rounds):
        if not pending_queries:
            break

        next_queries = []
        for q in pending_queries:
            context_data = build_local_context(q, graph, max_entities=8)
            if not context_data:
                continue

            prompt = drift_template.replace("{context_data}", context_data).replace(
                "{response_type}", response_type
            ).replace("{global_query}", query).replace(
                "{followups}", str(num_followups)
            )
            prompt += f"\n\n---User Question---\n{q}"

            print(f"  DRIFT 라운드 {round_idx + 1}: '{q[:50]}...'")
            raw = call_claude(prompt)

            try:
                result = parse_claude_response(raw)
                response_text = result.get("response", "")
                score = result.get("score", 0)
                follow_ups = result.get("follow_up_queries", [])
            except (ValueError, json.JSONDecodeError):
                response_text = _extract_text_response(raw)
                score = 50
                follow_ups = []

            # 라운드별 답변에서 언급된 노드 추적
            for nid in _extract_mentioned_nodes(response_text, graph):
                all_activated_nodes.add(nid)

            round_results.append({
                "query": q,
                "response": response_text,
                "score": score,
                "round": round_idx + 1,
            })

            # 점수가 충분하면 후속 질문 추가
            if score >= 30:
                next_queries.extend(follow_ups[:num_followups])

        pending_queries = next_queries

    # Reduce 단계: 모든 라운드 결과를 통합
    if not round_results:
        return {
            "answer": "관련된 정보를 찾을 수 없습니다.",
            "activated_nodes": [],
            "activated_communities": [],
            "rounds": [],
        }

    context_reports = "\n\n".join(
        f"--- Round {r['round']}: {r['query']} (score: {r['score']}) ---\n{r['response']}"
        for r in round_results
    )

    reduce_prompt = reduce_template.replace("{context_data}", context_reports).replace(
        "{response_type}", response_type
    )
    reduce_prompt += f"\n\n---User Question---\n{query}"

    print("  DRIFT Reduce: 통합 답변 생성...")
    raw = call_claude(reduce_prompt)
    answer = _extract_text_response(raw)

    # 최종 답변에서 언급된 노드도 추가
    for nid in _extract_mentioned_nodes(answer, graph):
        all_activated_nodes.add(nid)

    activated_communities = list({
        node_index[nid].get("communityId")
        for nid in all_activated_nodes
        if nid in node_index and node_index[nid].get("communityId")
    })

    return {
        "answer": answer,
        "activated_nodes": list(all_activated_nodes),
        "activated_communities": activated_communities,
        "rounds": round_results,
    }


def _extract_text_response(raw: str) -> str:
    """Claude 응답에서 텍스트를 추출한다 (JSON wrapper 제거)."""
    try:
        outer = json.loads(raw)
        return outer.get("result", raw)
    except (json.JSONDecodeError, TypeError):
        return raw.strip()
