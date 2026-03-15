#!/usr/bin/env python3
"""
Explainable GraphRAG 데이터셋 구축 스크립트
- 노드: reasoning, insight 필드 추가
- 커뮤니티: communityId, communityName, communitySummary 할당
- 링크: sourceContext 필드 추가 (원본 텍스트 발췌)
"""

import json
import os
import re
from pathlib import Path

from enrich_constants import TYPE_REASONING, COMMUNITIES

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "data" / "input"
# graph_advanced.json이 존재하면 우선 사용, 없으면 graph.json 폴백(fallback)
_GRAPH_ADVANCED = BASE_DIR / "data" / "output" / "graph_advanced.json"
_GRAPH_DEFAULT = BASE_DIR / "data" / "output" / "graph.json"
GRAPH_PATH = _GRAPH_ADVANCED if _GRAPH_ADVANCED.exists() else _GRAPH_DEFAULT
OUTPUT_PATH = BASE_DIR / "frontend" / "src" / "data.json"
COMMUNITIES_PATH = BASE_DIR / "data" / "output" / "communities.json"

# ─── 1. 데이터 로드 ───

with open(GRAPH_PATH, encoding="utf-8") as f:
    graph = json.load(f)

# 모든 입력 텍스트 로드 (파일명 → 내용)
texts = {}
for p in INPUT_DIR.glob("*.txt"):
    with open(p, encoding="utf-8") as f:
        texts[p.stem] = f.read()

# 노드 ID → 노드 객체 매핑
node_map = {n["id"]: n for n in graph["nodes"]}

# ─── 2. 타입 분류 추론 근거(reasoning) 생성 ───

def generate_reasoning(node):
    """노드의 type과 description 기반으로 분류 추론 근거 생성"""
    base = TYPE_REASONING.get(node["type"], "분류 근거 불명")
    desc = node.get("description", "")
    name = node["name"]

    # 구체적 근거 추가
    specifics = []
    if node["type"] == "person":
        # 직책/역할 키워드 탐지
        role_keywords = ["운동가", "의사", "기자", "선교사", "총독", "황제", "천황",
                         "지도자", "소설가", "교육인", "정치인", "역사학자", "대통령",
                         "주동자", "책임자", "비서", "지사", "대표", "의장", "부주석"]
        found = [kw for kw in role_keywords if kw in desc]
        if found:
            specifics.append(f"설명에서 '{', '.join(found)}' 등 개인 역할·직책 키워드가 확인됨")
    elif node["type"] == "organization":
        org_keywords = ["단체", "정당", "조직", "기관", "학교", "신문", "대학", "회",
                        "부대", "사단", "연대", "군", "연합", "위원부"]
        found = [kw for kw in org_keywords if kw in desc or kw in name]
        if found:
            specifics.append(f"명칭 또는 설명에서 '{', '.join(found)}' 등 조직 관련 키워드가 확인됨")
    elif node["type"] == "event":
        event_keywords = ["운동", "전투", "사건", "참변", "학살", "조약", "병합",
                          "의거", "선언", "회의", "전쟁", "장례", "인산", "총회", "해체"]
        found = [kw for kw in event_keywords if kw in desc or kw in name]
        if found:
            specifics.append(f"명칭 또는 설명에서 '{', '.join(found)}' 등 사건 관련 키워드가 확인됨")
    elif node["type"] == "location":
        loc_keywords = ["지역", "도시", "현", "군", "성", "역", "촌", "동", "형무소",
                        "학교", "마을", "강당", "수도"]
        found = [kw for kw in loc_keywords if kw in desc or kw in name]
        if found:
            specifics.append(f"명칭 또는 설명에서 '{', '.join(found)}' 등 장소 관련 키워드가 확인됨")
    elif node["type"] == "concept":
        con_keywords = ["주의", "이념", "운동", "작전", "계획", "원칙", "전략"]
        found = [kw for kw in con_keywords if kw in desc or kw in name]
        if found:
            specifics.append(f"명칭 또는 설명에서 '{', '.join(found)}' 등 개념 관련 키워드가 확인됨")

    if specifics:
        return f"{base} {specifics[0]}."
    return base


# ─── 3. 역사적 중요도(insight) 생성 ───

def generate_insight(node):
    """노드의 description, degree, type 기반으로 역사적 중요도 생성"""
    name = node["name"]
    desc = node.get("description", "")
    degree = node.get("degree", 0)
    ntype = node["type"]

    parts = []

    # 연결도 기반 중요도
    if degree >= 20:
        parts.append(f"{name}은(는) 그래프 내 {degree}개의 연결을 갖고 있어 독립운동 네트워크의 핵심 허브에 해당한다")
    elif degree >= 10:
        parts.append(f"{name}은(는) {degree}개의 연결을 갖고 있어 독립운동사에서 중요한 위치를 차지한다")
    elif degree >= 5:
        parts.append(f"{name}은(는) {degree}개의 연결을 갖고 있어 독립운동 네트워크에서 유의미한 역할을 수행했다")

    # 타입별 추가 통찰
    if ntype == "person":
        if any(kw in desc for kw in ["총독", "천황", "제국"]):
            parts.append("일제 식민통치 체제의 핵심 인물로, 독립운동과의 대립 관계를 이해하는 데 필수적이다")
        elif any(kw in desc for kw in ["임시정부", "대통령", "주석", "부주석", "의장"]):
            parts.append("대한민국 임시정부의 주요 지도자로, 독립운동의 조직적·외교적 측면을 대표한다")
        elif any(kw in desc for kw in ["의거", "저격", "폭탄", "암살"]):
            parts.append("무장 의열투쟁의 실행자로, 일제에 대한 직접적 무력 저항의 상징이다")
        elif any(kw in desc for kw in ["교육", "학교", "계몽"]):
            parts.append("교육·계몽 활동을 통해 민족의식을 고양한 인물이다")
        elif any(kw in desc for kw in ["사회주의", "공산"]):
            parts.append("사회주의 계열 독립운동을 이끈 인물로, 이념적 다양성을 보여준다")
        else:
            parts.append("독립운동 참여자로서 항일 저항의 역사를 증언하는 인물이다")
    elif ntype == "organization":
        if any(kw in desc for kw in ["임시정부"]):
            parts.append("대한민국의 법통을 이어받은 핵심 기관으로 독립운동사에서 최상위 중요도를 지닌다")
        elif any(kw in desc for kw in ["군", "부대", "사단"]):
            parts.append("무장 독립투쟁의 군사적 기반으로, 항일 전투사의 핵심 주체이다")
        elif any(kw in desc for kw in ["일본", "총독부", "제국"]):
            parts.append("식민 지배 체제의 구성 요소로, 독립운동 탄압의 주체를 이해하는 데 중요하다")
        else:
            parts.append("독립운동의 조직적 기반으로, 민족운동의 체계화에 기여했다")
    elif ntype == "event":
        if any(kw in desc for kw in ["전국", "만세"]):
            parts.append("전국적 규모의 항일 운동으로, 민족적 저항 의지를 상징하는 사건이다")
        elif any(kw in desc for kw in ["전투", "승리"]):
            parts.append("독립군의 군사적 성과를 보여주는 전투로, 무장 독립운동사의 분수령이다")
        elif any(kw in desc for kw in ["학살", "참변"]):
            parts.append("일제의 잔학 행위를 증명하는 사건으로, 식민 지배의 폭력성을 고발한다")
        elif any(kw in desc for kw in ["조약", "병합", "늑약"]):
            parts.append("한국의 국권 상실 과정을 보여주는 사건으로, 독립운동의 원인을 이해하는 데 핵심적이다")
        else:
            parts.append("독립운동사의 중요한 사건으로, 역사적 맥락 이해에 기여한다")
    elif ntype == "location":
        if any(kw in desc for kw in ["거점", "무대", "근거지"]):
            parts.append("독립운동의 핵심 활동 거점으로, 공간적 맥락을 파악하는 데 중요하다")
        elif any(kw in desc for kw in ["학살", "참변", "형무소"]):
            parts.append("일제 탄압·학살의 현장으로, 역사적 기억과 추모의 장소이다")
        else:
            parts.append("독립운동 관련 사건이 발생한 장소로, 역사적 공간 맥락을 제공한다")
    elif ntype == "concept":
        parts.append("독립운동의 이념적·전략적 기반을 이루는 개념으로, 운동의 방향성과 동기를 설명한다")

    return ". ".join(parts) + "."


def _load_leiden_communities() -> dict | None:
    """Leiden 커뮤니티 탐지 결과를 로드한다. 없으면 None 반환."""
    if not COMMUNITIES_PATH.exists():
        return None
    with open(COMMUNITIES_PATH, encoding="utf-8") as f:
        return json.load(f)


# Leiden 결과 캐싱 (한 번만 로드)
_leiden_data = _load_leiden_communities()


def assign_community(node):
    """노드를 커뮤니티에 할당한다.

    Leiden 결과가 존재하면 우선 사용하고, 없으면 수동 매칭으로 폴백한다.
    """
    node_id = node["id"]

    # Leiden 결과 우선 사용
    if _leiden_data is not None:
        membership = _leiden_data.get("membership", {})
        if node_id in membership:
            comm_idx = membership[node_id]
            # 고립 노드(-1)는 uncategorized
            if comm_idx == -1:
                return "uncategorized"
            # communities 리스트에서 해당 인덱스의 커뮤니티 ID 찾기
            for comm in _leiden_data.get("communities", []):
                if comm["index"] == comm_idx:
                    return comm["id"]

    # 폴백(fallback): 수동 매칭
    return _assign_community_manual(node)


def _assign_community_manual(node):
    """수동 커뮤니티 할당 (ID, 이름, 키워드 기반 폴백)"""
    node_id = node["id"]
    node_name = node["name"]
    node_desc = node.get("description", "").lower()

    # 1단계: ID 매칭
    for comm_id, comm in COMMUNITIES.items():
        if node_id in comm["node_ids"]:
            return comm_id

    # 2단계: 이름 매칭 (정규화된 이름으로 비교)
    norm_name = node_name.split("(")[0].strip()
    for comm_id, comm in COMMUNITIES.items():
        for cid in comm["node_ids"]:
            if norm_name in cid or cid in node_id:
                return comm_id

    # 3단계: 키워드 매칭
    for comm_id, comm in COMMUNITIES.items():
        if any(kw in node_name or kw in node_desc for kw in comm["keywords"]):
            return comm_id

    return "uncategorized"


# ─── 5. 원본 텍스트 발췌(sourceContext) 검색 ───

def find_source_context(source_node, target_node, max_len=200):
    """두 노드와 관련된 원본 텍스트 발췌문을 검색"""
    s_name = source_node["name"]
    t_name = target_node["name"]

    # 검색 이름 변형 생성
    s_variants = _name_variants(s_name)
    t_variants = _name_variants(t_name)

    best_context = ""
    best_score = 0

    for fname, content in texts.items():
        sentences = re.split(r'[.。\n]+', content)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 10:
                continue

            s_found = any(v in sent for v in s_variants)
            t_found = any(v in sent for v in t_variants)

            if s_found and t_found:
                # 두 노드 모두 언급된 문장 → 최고 점수
                score = 3
            elif s_found or t_found:
                score = 1
            else:
                continue

            if score > best_score or (score == best_score and len(sent) > len(best_context)):
                best_score = score
                best_context = sent[:max_len]
                if best_score == 3:
                    break  # 최적 매치 발견
        if best_score == 3:
            break

    if not best_context:
        # 대안: 소스 노드의 설명 + 타겟 노드의 설명 기반 근거
        best_context = f"{s_name}의 설명({source_node.get('description', '')})과 {t_name}의 설명({target_node.get('description', '')})에서 관계가 유추됨"

    return best_context


def _name_variants(name):
    """이름의 검색 변형 생성"""
    variants = [name]
    # 가운데점 변형
    if "·" in name:
        variants.append(name.replace("·", " "))
        variants.append(name.replace("·", ""))
        variants.append(name.replace("·", "˙"))
    # 공백 제거 변형
    if " " in name:
        variants.append(name.replace(" ", ""))
    # 약칭 (3자 이상 이름의 경우)
    if len(name) >= 3 and not any(c in name for c in "· "):
        variants.append(name[:2])  # 성+이름 첫 글자
    return variants


# ─── 6. 메인 처리 ───

print("=== Explainable GraphRAG 데이터셋 구축 시작 ===")
print(f"입력 노드: {len(graph['nodes'])}개, 링크: {len(graph['links'])}개")
print(f"입력 텍스트: {len(texts)}개 파일")

# Leiden 커뮤니티 이름/요약 인덱스 구축
_leiden_comm_index: dict[str, dict] = {}
if _leiden_data is not None:
    for comm in _leiden_data.get("communities", []):
        _leiden_comm_index[comm["id"]] = {
            "name": comm["name"],
            "summary": "",  # LLM 리포트에서 채움
        }
    # LLM 리포트에서 summary 로드
    _report_path = BASE_DIR / "data" / "output" / "community_reports.json"
    if _report_path.exists():
        with open(_report_path, encoding="utf-8") as _rf:
            for _report in json.load(_rf):
                _cid = _report.get("community_id", "")
                if _cid in _leiden_comm_index:
                    _leiden_comm_index[_cid]["summary"] = _report.get("summary", "")


def _get_community_info(comm_id: str) -> dict:
    """커뮤니티 ID로 이름과 요약을 반환한다."""
    # Leiden 결과 우선
    if comm_id in _leiden_comm_index:
        info = _leiden_comm_index[comm_id]
        return {
            "name": info["name"],
            "summary": info["summary"] or "Leiden 알고리즘으로 탐지된 커뮤니티.",
        }
    # 수동 커뮤니티 폴백
    if comm_id in COMMUNITIES:
        return {
            "name": COMMUNITIES[comm_id]["name"],
            "summary": COMMUNITIES[comm_id]["summary"],
        }
    return {
        "name": "기타 독립운동 관련",
        "summary": "주요 커뮤니티에 직접 포함되지 않으나 독립운동사와 관련된 노드.",
    }


# 6-1. 노드 보강
enriched_nodes = []
community_stats = {}

for node in graph["nodes"]:
    comm_id = assign_community(node)
    comm = _get_community_info(comm_id)

    node["reasoning"] = generate_reasoning(node)
    node["insight"] = generate_insight(node)
    node["communityId"] = comm_id
    node["communityName"] = comm["name"]
    node["communitySummary"] = comm["summary"]

    enriched_nodes.append(node)

    community_stats[comm_id] = community_stats.get(comm_id, 0) + 1

# 6-2. 링크 보강
enriched_links = []
context_found_count = 0
context_inferred_count = 0

for link in graph["links"]:
    src_id = link["source"]
    tgt_id = link["target"]
    src_node = node_map.get(src_id, {"name": src_id, "description": ""})
    tgt_node = node_map.get(tgt_id, {"name": tgt_id, "description": ""})

    context = find_source_context(src_node, tgt_node)
    link["sourceContext"] = context

    if "유추됨" in context:
        context_inferred_count += 1
    else:
        context_found_count += 1

    enriched_links.append(link)

# 6-3. 커뮤니티 목록 생성
communities = []

if _leiden_data is not None:
    # Leiden 결과 기반 커뮤니티 목록
    for comm in _leiden_data.get("communities", []):
        comm_id = comm["id"]
        # 수동 커뮤니티에서 summary 가져오기 (있으면)
        manual_comm = COMMUNITIES.get(comm_id, {})
        # community_reports.json에서 LLM 리포트 가져오기 (있으면)
        report_path = BASE_DIR / "data" / "output" / "community_reports.json"
        llm_summary = ""
        if report_path.exists():
            with open(report_path, encoding="utf-8") as f:
                reports = json.load(f)
            for report in reports:
                if report.get("community_id") == comm_id:
                    llm_summary = report.get("summary", "")
                    break

        communities.append({
            "id": comm_id,
            "name": comm["name"],
            "summary": llm_summary or manual_comm.get("summary", f"Leiden 알고리즘으로 탐지된 커뮤니티."),
            "nodeCount": community_stats.get(comm_id, 0)
        })
else:
    # 폴백: 수동 커뮤니티 목록
    for comm_id, comm in COMMUNITIES.items():
        communities.append({
            "id": comm_id,
            "name": comm["name"],
            "summary": comm["summary"],
            "nodeCount": community_stats.get(comm_id, 0)
        })

# uncategorized 커뮤니티 추가 (해당 노드가 있는 경우)
if "uncategorized" in community_stats:
    communities.append({
        "id": "uncategorized",
        "name": "기타 독립운동 관련",
        "summary": "주요 커뮤니티에 직접 포함되지 않으나 독립운동사와 관련된 노드.",
        "nodeCount": community_stats["uncategorized"]
    })

# 6-4. 결과 저장
output = {
    "nodes": enriched_nodes,
    "links": enriched_links,
    "communities": communities
}

os.makedirs(OUTPUT_PATH.parent, exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

# ─── 7. 요약 보고 ───
print("\n=== 보강 완료 ===")
print(f"총 노드: {len(enriched_nodes)}개")
print(f"  - reasoning 필드 추가: {len(enriched_nodes)}개")
print(f"  - insight 필드 추가: {len(enriched_nodes)}개")
print(f"  - 커뮤니티 할당: {len(enriched_nodes)}개")
print(f"총 링크: {len(enriched_links)}개")
print(f"  - 원본 텍스트 발췌 성공: {context_found_count}개")
print(f"  - 설명 기반 유추: {context_inferred_count}개")
print(f"\n커뮤니티 분포:")
for comm_id, count in sorted(community_stats.items(), key=lambda x: -x[1]):
    cinfo = _get_community_info(comm_id)
    print(f"  {cinfo['name']}: {count}개 노드")
print(f"\n결과 저장: {OUTPUT_PATH}")
