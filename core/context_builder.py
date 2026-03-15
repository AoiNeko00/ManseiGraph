"""검색 컨텍스트 조립(context building) 모듈.

Local Search와 Global Search에 필요한 컨텍스트 데이터를 구성한다.
임베딩이 존재하면 의미 검색을, 없으면 키워드 매칭을 사용한다.
"""

import json
import re
from pathlib import Path

from core.graph_utils import build_node_index

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_PATH = BASE_DIR / "data" / "output" / "community_reports.json"
COMMUNITIES_PATH = BASE_DIR / "data" / "output" / "communities.json"
CLAIMS_PATH = BASE_DIR / "data" / "output" / "claims.json"

# 임베딩 캐시 (lazy loading)
_embeddings_cache = None


def _get_embeddings():
    """임베딩 데이터를 로드한다 (캐시, lazy)."""
    global _embeddings_cache
    if _embeddings_cache is None:
        from core.embedding import load_embeddings
        _embeddings_cache = load_embeddings()  # None이면 미생성 상태
    return _embeddings_cache


def find_relevant_entities(
    query: str,
    graph: dict,
    max_entities: int = 10,
) -> list[dict]:
    """질의와 관련된 엔티티를 찾는다.

    임베딩이 존재하면 의미 검색(semantic search) + 키워드 부스트를 사용하고,
    없으면 키워드 매칭으로 폴백한다.

    Args:
        query: 사용자 질의 문자열.
        graph: 그래프 데이터.
        max_entities: 반환할 최대 엔티티 수.

    Returns:
        관련도 순으로 정렬된 노드 리스트.
    """
    emb_data = _get_embeddings()
    node_index = build_node_index(graph)

    if emb_data is not None:
        return _find_by_embedding(
            query, graph, node_index, emb_data, max_entities,
        )

    return _find_by_keyword(query, graph, max_entities)


def _find_by_embedding(
    query: str,
    graph: dict,
    node_index: dict,
    emb_data: tuple,
    max_entities: int,
) -> list[dict]:
    """임베딩 기반 의미 검색 + 키워드 부스트."""
    from core.embedding import semantic_search

    embeddings, node_ids = emb_data
    semantic_results = semantic_search(
        query, embeddings, node_ids, top_k=max_entities * 2,
    )

    # 키워드 부스트: 이름 직접 매칭 시 유사도에 가산
    query_lower = query.lower()
    boosted = []
    for node_id, sim_score in semantic_results:
        node = node_index.get(node_id)
        if node is None:
            continue
        name = node.get("name", "").lower()
        boost = 0.3 if name in query_lower or query_lower in name else 0.0
        boosted.append((sim_score + boost, node))

    # 키워드 전용 매칭으로 누락된 노드 보완
    keyword_results = _find_by_keyword(query, graph, max_entities)
    seen_ids = {n["id"] for _, n in boosted}
    for node in keyword_results:
        if node["id"] not in seen_ids:
            boosted.append((0.5, node))  # 키워드 매칭 기본 점수

    boosted.sort(key=lambda x: -x[0])
    return [node for _, node in boosted[:max_entities]]


def _find_by_keyword(
    query: str,
    graph: dict,
    max_entities: int,
) -> list[dict]:
    """키워드 매칭 기반 엔티티 검색 (폴백)."""
    query_lower = query.lower()
    query_tokens = set(re.split(r'\s+', query_lower))

    scored_nodes = []
    for node in graph["nodes"]:
        score = _compute_relevance_score(node, query_lower, query_tokens)
        if score > 0:
            scored_nodes.append((score, node))

    scored_nodes.sort(key=lambda x: -x[0])
    return [node for _, node in scored_nodes[:max_entities]]


def _compute_relevance_score(
    node: dict,
    query_lower: str,
    query_tokens: set[str],
) -> float:
    """노드와 질의 간 관련도 점수를 계산한다."""
    name = node.get("name", "").lower()
    desc = node.get("description", "").lower()
    score = 0.0

    # 이름 완전 일치 (최고 점수)
    if name in query_lower or query_lower in name:
        score += 10.0

    # 이름 토큰 매칭
    name_tokens = set(re.split(r'\s+', name))
    overlap = query_tokens & name_tokens
    score += len(overlap) * 3.0

    # 설명 키워드 매칭
    for token in query_tokens:
        if len(token) >= 2 and token in desc:
            score += 1.0

    # degree 가산 (중요 노드 선호)
    if score > 0:
        score += min(node.get("degree", 0) * 0.1, 2.0)

    return score


def build_local_context(
    query: str,
    graph: dict,
    max_entities: int = 10,
    max_relationships: int = 30,
) -> str:
    """Local Search용 컨텍스트 데이터를 조립한다.

    관련 엔티티 + 연결된 관계 + 소속 커뮤니티 요약을 포함한다.
    """
    entities = find_relevant_entities(query, graph, max_entities)
    if not entities:
        return ""

    entity_ids = {e["id"] for e in entities}
    node_index = build_node_index(graph)

    # 관련 엔티티의 이웃도 포함 (1-hop 확장)
    extended_ids = set(entity_ids)
    for link in graph["links"]:
        if link["source"] in entity_ids:
            extended_ids.add(link["target"])
        if link["target"] in entity_ids:
            extended_ids.add(link["source"])

    # 엔티티 테이블
    sections = ["---Entities---\n"]
    sections.append("id,name,type,description")
    for eid in extended_ids:
        node = node_index.get(eid)
        if node:
            sections.append(
                f"{eid},{node.get('name','')},{node.get('type','')},{node.get('description','')}"
            )

    # 관계 테이블
    sections.append("\n---Relationships---\n")
    sections.append("id,source,target,relation,description")
    rel_count = 0
    for link in graph["links"]:
        if rel_count >= max_relationships:
            break
        if link["source"] in extended_ids and link["target"] in extended_ids:
            src_name = node_index.get(link["source"], {}).get("name", link["source"])
            tgt_name = node_index.get(link["target"], {}).get("name", link["target"])
            desc = link.get("description", link.get("relation", ""))
            sections.append(f"{rel_count},{src_name},{tgt_name},{link.get('relation','')},{desc}")
            rel_count += 1

    # 커뮤니티 리포트 (관련 엔티티의 소속 커뮤니티)
    community_summaries = _get_relevant_community_summaries(entities)
    if community_summaries:
        sections.append("\n---Community Reports---\n")
        for i, summary in enumerate(community_summaries):
            sections.append(f"Report {i}: {summary}")

    # Claims (관련 엔티티의 역사적 주장/사실)
    claims_data = _get_relevant_claims(entities)
    if claims_data:
        sections.append("\n---Claims---\n")
        sections.append("id,subject,object,claim_type,status,description")
        for i, claim in enumerate(claims_data):
            sections.append(
                f"{i},{claim['subject']},{claim['object']},"
                f"{claim['claim_type']},{claim['status']},{claim['description']}"
            )

    return "\n".join(sections)


def build_global_context(
    max_reports: int = 20,
    level: int | None = None,
) -> list[dict]:
    """Global Search용 커뮤니티 리포트 목록을 로드한다.

    Args:
        max_reports: 최대 리포트 수.
        level: 계층 레벨 필터. None이면 전체, 0=대분류, 1=기본, 2=세분류.

    Returns:
        커뮤니티 리포트 리스트. 각 항목은
        {"id": int, "title": str, "summary": str, "content": str} 형태.
    """
    if not REPORTS_PATH.exists():
        return []

    with open(REPORTS_PATH, encoding="utf-8") as f:
        all_reports = json.load(f)

    # 레벨 필터: 계층 데이터가 있으면 해당 레벨만
    if level is not None:
        all_reports = [r for r in all_reports if r.get("level", 1) == level]

    result = []
    for i, report in enumerate(all_reports[:max_reports]):
        content_parts = [report.get("summary", "")]
        for finding in report.get("findings", []):
            content_parts.append(
                f"- {finding.get('summary', '')}: {finding.get('explanation', '')}"
            )
        result.append({
            "id": i,
            "title": report.get("title", f"Community {i}"),
            "summary": report.get("summary", ""),
            "content": "\n".join(content_parts),
            "community_id": report.get("community_id", ""),
            "level": report.get("level", 1),
        })

    return result


def format_global_context_chunk(
    reports: list[dict],
) -> str:
    """Global Search Map 단계용 컨텍스트 청크를 포맷한다."""
    sections = ["---Community Reports---\n"]
    for report in reports:
        sections.append(
            f"Report {report['id']}: {report['title']}\n{report['content']}\n"
        )
    return "\n".join(sections)


def _get_relevant_claims(entities: list[dict]) -> list[dict]:
    """관련 엔티티의 Claims를 가져온다."""
    if not CLAIMS_PATH.exists():
        return []

    with open(CLAIMS_PATH, encoding="utf-8") as f:
        all_claims = json.load(f)

    result = []
    for entity in entities:
        name = entity.get("name", "")
        base_name = name.split("(")[0].strip()
        # claims.json은 {이름: [claim, ...]} 형태
        if base_name in all_claims:
            result.extend(all_claims[base_name][:5])  # 엔티티당 최대 5개

    return result[:20]  # 총 최대 20개


def _get_relevant_community_summaries(entities: list[dict]) -> list[str]:
    """관련 엔티티의 소속 커뮤니티 요약을 가져온다."""
    if not REPORTS_PATH.exists():
        return []

    with open(REPORTS_PATH, encoding="utf-8") as f:
        reports = json.load(f)

    # 엔티티의 communityId 수집
    comm_ids = {e.get("communityId") for e in entities if e.get("communityId")}

    summaries = []
    report_by_id = {r.get("community_id"): r for r in reports}
    for comm_id in comm_ids:
        report = report_by_id.get(comm_id)
        if report:
            summaries.append(report.get("summary", ""))

    return summaries
