# ManseiGraph

GraphRAG 논문(Microsoft, "From Local to Global")의 파이프라인을 직접 구현하여 동작 원리를 학습하기 위한 프로젝트.
한국 독립운동사 위키피디아 데이터를 입력으로, 추출 → 커뮤니티 탐지 → 요약 → 검색 → 시각화까지 전 과정을 구현했다.

---

## 논문과의 대조

### 논문과 동일하게 구현한 부분

| 논문 단계 | 구현 |
|-----------|------|
| LLM 기반 엔티티/관계 추출 | Claude Opus로 2-pass 추출 (기본 추출 → 누락 관계 재탐색) |
| Leiden 커뮤니티 탐지 | igraph + leidenalg, 다중 해상도(0.3/1.0/2.5) 계층적 탐지 지원 |
| LLM 커뮤니티 요약 | 커뮤니티별 노드/관계를 프롬프트에 주입하여 구조화된 리포트 생성 (title, summary, rating, findings) |
| Local Search | 관련 엔티티 + 1-hop 이웃 + 커뮤니티 요약을 컨텍스트로 LLM에 전달 |
| Global Search (Map-Reduce) | 커뮤니티 리포트를 청크 분할 → Map(핵심 포인트 추출) → 중요도 정렬 → Reduce(통합 답변) |
| DRIFT Search | 로컬에서 시작 → 후속 질문 자동 생성 → 점진적 컨텍스트 확장 → Reduce |
| Claim 추출 | 엔티티별 역사적 주장/사실을 추출하고 검증 상태(TRUE/SUSPECTED/FALSE)를 부여 |

### 논문과 다르게 처리한 부분

| 항목 | 논문 | 이 프로젝트 |
|------|------|-------------|
| Text Unit 인덱스 | 원본 텍스트 청크를 엔티티/관계에 역매핑하여 검색 시 활용 | sourceContext(원본 발췌문)로 대체. 체계적 역매핑은 미구현 |
| 엔티티 검색 방식 | text_unit 임베딩 → 관련 엔티티 역추적 | 노드 description 임베딩으로 직접 검색 + 키워드 부스트 |
| Covariate 저장 | 엔티티 속성(날짜, 상태 등)을 별도 테이블로 관리 | 미구현. description 필드에 포함 |
| 시각화 | 논문 범위 밖 | 그래프 탐색 UI + 검색 결과 하이라이트 + 추출 근거 확인 (이 프로젝트 고유) |
| 활성화 노드 추적 | 논문 범위 밖 | 답변 텍스트에서 노드명 매칭 + Citation 패턴 파싱으로 추출 (이 프로젝트 고유) |
| 동명이인 처리 | 논문에서 별도 언급 없음 | LLM 기반 동명이인 판별 + ID 분리/병합 (도메인 특화) |
| 의미 기반 중복 제거 | 논문에서 별도 언급 없음 | 이름 정규화 + 동의어 접미사 + 임베딩 유사도로 중복 노드 탐지/병합 |

---

## 개요

| 항목 | 내용 |
|------|------|
| 데이터 | 위키피디아 한국어 독립운동 관련 문서 50개 |
| 추출 | Claude CLI (Opus 모델, subprocess 호출) |
| 커뮤니티 탐지 | Leiden 알고리즘 (igraph + leidenalg, 모듈러리티 0.60, 11개 커뮤니티) |
| 커뮤니티 요약 | LLM 기반 리포트 생성 (IMPACT RATING + findings) |
| 검색 | Local + Global (Map-Reduce) + DRIFT |
| 임베딩 | paraphrase-multilingual-MiniLM-L12-v2 (384차원) |
| 프론트엔드 | React 19 + TypeScript + react-force-graph-2d |
| 규모 | 810 노드, 2,263 엣지, 249종 관계 타입 |
| 테스트 | pytest 25개 |

---

## 실행

### 통합 실행
```bash
./start.sh
```
API 서버(`:8000`)와 프론트엔드(`:5173`)를 동시에 시작한다. `Ctrl+C`로 종료.

### 시각화만
```bash
cd frontend && npm install && npm run dev
```

### 데이터 재구축
```bash
pip install python-igraph leidenalg sentence-transformers numpy fastapi uvicorn

# 그래프 추출 (Claude Opus 필요)
python3 preprocess_graph.py
python3 scripts/extract_advanced.py

# 파이프라인 일괄 실행 (탐지 → 리포트 → 보강 → 임베딩)
python3 pipeline.py                    # 완료된 단계 건너뛰고 이어서 실행
python3 pipeline.py --force            # 전체 재실행
python3 pipeline.py --hierarchical     # 계층적 커뮤니티 포함 (3단계 해상도)

# Claim 추출
# 기본값은 degree 상위 20명만 추출 (LLM 호출 비용 제한)
# 범위를 넓히려면 scripts/extract_claims.py의 MAX_ENTITIES 값을 변경
# 이미 추출된 인물은 캐시되므로 값을 올려서 재실행하면 추가분만 처리됨
python3 scripts/extract_claims.py

# 테스트 후 실행
python3 -m pytest tests/ -v
./start.sh
```

---

## 파이프라인

```
data/input/*.txt (위키피디아 50개 문서)
     │
     ▼
1. Knowledge Graph 구축
   preprocess_graph.py
   ├ Pass 1: 엔티티/관계 추출
   ├ 동명이인 감지 (LLM 기반)
   └ Pass 2: 누락 관계 재탐색

   scripts/extract_advanced.py
   ├ 동명이인 문맥 분석
   ├ 고립 노드 관계 보강
   └ 중요도 가중치 산출
     │ graph_advanced.json
     ▼
2. Community Detection
   scripts/detect_communities.py
   ├ Leiden 알고리즘 (igraph + leidenalg)
   ├ 소규모 커뮤니티 병합 (min_size=3)
   └ 모듈러리티 산출
     │ communities.json
     ▼
3. Community Summary
   scripts/generate_community_reports.py
   ├ 커뮤니티별 노드/링크 → 프롬프트 주입
   └ Claude Opus로 구조화된 리포트 생성
     │ community_reports.json
     ▼
4. Enrichment + Embedding
   scripts/enrich_graph.py
   ├ reasoning, insight, community 할당
   └ sourceContext (원본 텍스트 발췌)

   scripts/build_embeddings.py
   └ 810개 노드 → 384차원 벡터
     │ data.json + embeddings.npz
     ▼
4b. Claim 추출 (선택)
   scripts/extract_claims.py
   ├ 주요 인물별 역사적 주장/사실 추출
   └ 검증 상태: TRUE / SUSPECTED / FALSE
     │ claims.json
     ▼
5. Search Engine
   server.py (FastAPI)
   ├ Local Search: 엔티티 중심 + 임베딩 유사도
   ├ Global Search: Map-Reduce 커뮤니티 기반
   └ DRIFT Search: 로컬 → 후속질문 → 확장 → 통합
     │ POST /api/search
     ▼
6. Visualization
   frontend/ (React + ForceGraph2D)
   ├ 자연어 질의 → 활성화 노드 하이라이트
   ├ 2-hop 이웃 포커스 + 커뮤니티 헐
   └ 추출 근거 + 원본 발췌문 표시
```

---

## UI에서 확인할 수 있는 것

### 노드 클릭 (우측 패널)
- **Reasoning:** 이 엔티티가 해당 타입으로 분류된 근거
- **Insight:** 네트워크 내에서의 위치와 역할 설명
- **Community:** 소속 커뮤니티의 LLM 생성 요약
- **연결 목록:** 관계 타입별 그룹, 가나다순 정렬

### 엣지 클릭 (하단 패널)
- **description:** LLM이 이 관계를 추출한 근거
- **sourceContext:** 위키피디아 원문에서 매칭된 발췌문
- **strength:** 관계 강도 1~10

### 자연어 질의 (우하단 패널)
- **Local:** 관련 엔티티 + 이웃 + 커뮤니티 리포트 기반 답변
- **DRIFT:** 로컬에서 시작, 후속 질문으로 탐색 범위를 넓혀 통합 답변
- **Global:** 전체 커뮤니티 리포트를 Map-Reduce로 종합
- 답변에 기여한 노드가 그래프에서 하이라이트됨

---

## 검색 API

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/api/health` | 헬스체크 |
| `POST` | `/api/search` | 자연어 검색 (Local/Global/DRIFT) |
| `GET` | `/api/claims/{name}` | 특정 엔티티의 Claims 조회 |

```json
// 요청
{ "query": "김구와 이승만의 관계는?", "search_type": "local" }

// 응답
{
  "answer": "김구(백범)와 이승만은...",
  "activated_nodes": ["kim_gu", "lee_seungman"],
  "activated_communities": ["auto_김구"],
  "search_type": "local"
}
```

`search_type`은 `"local"`, `"global"`, `"drift"` 중 하나.

---

## 시각 인코딩

| 요소 | 규칙 |
|------|------|
| 노드 형태 | 인물=원, 단체=육각형, 사건=다이아몬드, 장소=둥근사각형, 개념=삼각형 |
| 노드 크기 | degree + 가중치 |
| 노드 색상 | 커뮤니티별 12색 팔레트 |
| 엣지 두께 | 관계 강도 (1~10) |
| 엣지 패턴 | 행위=실선, 구조=긴점선, 영향=짧은점선, 공간=점 |
| 커뮤니티 헐 | 반투명 볼록 껍질 |
| 검색 하이라이트 | 활성화 노드에 호박색 외곽 링 |

### 키보드 단축키

| 키 | 기능 |
|----|------|
| `Cmd+K` / `/` | Quick Search |
| `ESC` | 패널 닫기 |
| `0` | 전체보기 |
| `R` | 초기화 |
| `+` / `-` | 줌 |

---

## 구조

```
ManseiGraph/
├── core/                              # 도메인 로직
│   ├── algorithms.py                  # 동명이인/고립노드/중요도 알고리즘
│   ├── claim_extractor.py             # Claim 추출 + 파싱
│   ├── claude_client.py               # Claude CLI 호출 (재시도, 타임아웃)
│   ├── community_detection.py         # Leiden 커뮤니티 탐지 (계층적 지원)
│   ├── community_report.py            # LLM 커뮤니티 리포트 생성
│   ├── constants.py                   # 가중치, 텍스트 길이 상수
│   ├── context_builder.py             # 검색 컨텍스트 조립 (Claims 포함)
│   ├── embedding.py                   # 임베딩 생성 + 유사도 검색 + 리포트 랭킹
│   ├── graph_merge.py                 # 병합, 중복제거, 동명이인 처리
│   ├── graph_utils.py                 # 그래프 I/O, degree 계산
│   ├── prompts.py                     # 추출 프롬프트 (EXTRACTION/CROSSCHECK/HOMONYM)
│   ├── prompts_advanced.py            # 고도화 프롬프트
│   ├── search_engine.py               # Local/Global/DRIFT 검색 + Citation 파싱
│   └── text_utils.py                  # 청킹, ID 정규화
├── scripts/
│   ├── build_embeddings.py            # 노드 임베딩 생성
│   ├── deduplicate_graph.py           # 이름 기반 중복 제거
│   ├── deduplicate_semantic.py        # 의미 기반 중복 제거 (임베딩 + 동의어)
│   ├── detect_communities.py          # Leiden 탐지 실행
│   ├── enrich_constants.py            # 커뮤니티 시드, 타입 추론 템플릿
│   ├── enrich_graph.py                # 데이터셋 보강
│   ├── extract_advanced.py            # 고도화 파이프라인
│   ├── extract_claims.py              # Claim 추출 실행
│   └── generate_community_reports.py  # 커뮤니티 리포트 생성
├── tests/                             # pytest (25개)
│   ├── test_community_detection.py
│   ├── test_context_builder.py
│   ├── test_embedding.py
│   ├── test_graph_utils.py
│   ├── test_server.py
│   └── test_text_utils.py
├── data/
│   ├── input/                         # 위키피디아 텍스트 (50개)
│   └── output/                        # 파이프라인 출력물
│       ├── graph.json                 # 1차 추출 결과
│       ├── graph_advanced.json        # 고도화 결과
│       ├── communities.json           # Leiden 탐지 결과 (계층 포함)
│       ├── community_reports.json     # LLM 커뮤니티 리포트
│       ├── embeddings.npz             # 노드 임베딩 (800x384)
│       ├── embedding_index.json       # 노드 ID ↔ 임베딩 인덱스
│       └── claims.json                # Claim 추출 결과
├── frontend/src/
│   ├── App.tsx, App.css               # 메인 컴포넌트
│   ├── types.ts, constants.ts, utils.ts
│   ├── data.json                      # 시각화용 최종 데이터
│   ├── hooks/                         # useGraphData, useCanvasRenderers, useGraphControls, useKeyboardShortcuts
│   └── components/                    # SidePanel, ContextPanel, QueryPanel, SearchModal, Legend
├── prompts/                           # GraphRAG 프롬프트 (13종)
├── pipeline.py                        # 파이프라인 오케스트레이터
├── server.py                          # FastAPI 검색 API
├── start.sh                           # 통합 실행 (API + 프론트엔드)
├── preprocess_graph.py                # 1차 추출 진입점
├── collect_data.py                    # 위키피디아 데이터 수집
└── settings.yaml                      # GraphRAG 설정
```

---

## 향후 과제

현재 구현하지 않은 항목과 그 이유, 향후 방향을 정리한다.

### 미구현 사항

| 항목 | 설명 | 미구현 사유 |
|------|------|------------|
| **Text Unit 인덱스** | 원본 텍스트 청크를 엔티티/관계에 역매핑하여, 검색 시 "이 정보가 원문 어느 구간에서 왔는지" 정확히 추적 | 추출 단계(`preprocess_graph.py`) 재실행이 필요하며, 50개 문서 전체를 다시 LLM에 통과시켜야 하므로 처리 시간과 API 사용량이 크다. sourceContext(원본 발췌문)로 부분 대체 중 |
| **Covariate 저장** | 엔티티의 날짜, 직책, 상태 등 속성을 별도 필드로 분리 관리 | 현재 description에 포함되어 있어 검색에는 지장 없음. 구조화하려면 추출 프롬프트 수정 + 재추출 필요 |
| **증분 업데이트** | 새 문서 추가 시 변경분만 그래프에 반영 | 현재는 전체 재인덱싱 방식. 문서 단위 diff + merge 로직이 추가되면 재추출 범위를 줄일 수 있다 |
| **전용 Vector DB** | ChromaDB, FAISS 등으로 임베딩 인덱스 교체 | 800노드 규모에서는 numpy 인메모리 계산으로 충분. 노드가 수만 개로 확장될 경우 필요 |
| **Claim 전체 추출** | 현재 degree 상위 20명만 추출 (전체 인물 994명 중) | 인물 1명당 LLM 호출 1회가 필요. `MAX_ENTITIES` 값을 올려 점진적 확장 가능 |

### 향후 방향

- **Text Unit 인덱스 도입** — 추출 단계에서 청크 ID를 엔티티/관계에 태깅하면, 검색 시 원문 구간까지 정확히 역추적할 수 있다. 논문과의 가장 큰 구조적 차이를 해소하는 작업이다. LLM 호출 없이 코드 로직만으로 구현 가능하나, 기존 그래프 재추출이 수반된다.
- **Covariate 파싱** — 기존 description에서 날짜(`r'\d{4}년'`), 직책 키워드를 정규식으로 추출하여 별도 필드로 분리. LLM 호출 불필요.
- **증분 업데이트** — 입력 파일의 수정 시간을 비교하여 변경된 파일만 재추출 → `graph_merge.py`로 기존 그래프에 병합. 재인덱싱 비용을 줄인다.

---

## Tech Stack

| 영역 | 기술 |
|------|------|
| Frontend | React 19, TypeScript 5.9, Vite 8, react-force-graph-2d, d3-force-3d |
| Backend | Python 3, FastAPI, Claude CLI (Opus) |
| Community Detection | igraph + leidenalg |
| Embedding | sentence-transformers (MiniLM-L12-v2, 384dim) |
| Data | 위키피디아 한국어 50개 문서, JSON |
| Test | pytest 25개 |
| Architecture | Clean Architecture, SRP |
