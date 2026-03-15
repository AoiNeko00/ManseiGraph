"""커뮤니티 리포트(community report) 생성 모듈.

커뮤니티별 소속 노드와 링크를 프롬프트에 주입하여
LLM 기반 커뮤니티 요약 리포트를 생성한다.
"""

from pathlib import Path

from core.claude_client import call_claude, parse_claude_response
from core.community_detection import get_community_links, group_communities

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "community_report_graph.txt"
MAX_REPORT_LENGTH = 1500  # 리포트 최대 단어 수


def load_prompt_template() -> str:
    """커뮤니티 리포트 프롬프트 템플릿을 로드한다."""
    with open(PROMPT_PATH, encoding="utf-8") as f:
        return f.read()


def format_community_context(
    nodes: list[dict],
    links: list[dict],
) -> str:
    """커뮤니티의 노드와 링크를 프롬프트에 주입할 텍스트로 변환한다."""
    lines = ["Entities\n", "human_readable_id,title,description"]
    for i, node in enumerate(nodes):
        title = node.get("name", node["id"])
        desc = node.get("description", "")
        lines.append(f"{i},{title},{desc}")

    lines.append("\nRelationships\n")
    lines.append("human_readable_id,source,target,description")
    node_names = {n["id"]: n.get("name", n["id"]) for n in nodes}
    for i, link in enumerate(links):
        src_name = node_names.get(link["source"], link["source"])
        tgt_name = node_names.get(link["target"], link["target"])
        desc = link.get("description", link.get("relation", "related_to"))
        lines.append(f"{i},{src_name},{tgt_name},{desc}")

    return "\n".join(lines)


def generate_community_report(
    graph: dict,
    membership: dict[str, int],
    community_idx: int,
    community_name: str,
) -> dict:
    """단일 커뮤니티의 LLM 기반 리포트를 생성한다.

    Returns:
        {"community_id": str, "title": str, "summary": str, "rating": float,
         "rating_explanation": str, "findings": list[dict]}
    """
    groups = group_communities(graph, membership)
    nodes = groups.get(community_idx, [])
    links = get_community_links(graph, membership, community_idx)

    if not nodes:
        return {
            "community_id": community_name,
            "title": community_name,
            "summary": "소속 노드가 없는 커뮤니티.",
            "rating": 0.0,
            "rating_explanation": "노드 없음",
            "findings": [],
        }

    template = load_prompt_template()
    context = format_community_context(nodes, links)
    prompt = template.replace("{input_text}", context).replace(
        "{max_report_length}", str(MAX_REPORT_LENGTH)
    )

    print(f"  [{community_idx}] {community_name}: "
          f"{len(nodes)}개 노드, {len(links)}개 링크 → Claude 호출...")

    raw = call_claude(prompt)
    report = parse_claude_response(raw)

    report["community_id"] = community_name
    return report
