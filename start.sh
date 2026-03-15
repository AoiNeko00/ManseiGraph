#!/bin/bash
# ManseiGraph 통합 실행 스크립트
# 검색 API 서버 + 프론트엔드 개발 서버를 동시에 시작한다.

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# 색상 정의
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ManseiGraph — Explainable GraphRAG         ║${NC}"
echo -e "${GREEN}║   한국 독립운동 지식 그래프                     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ─── 사전 검증 ───

# data.json 존재 확인
if [ ! -f "frontend/src/data.json" ]; then
  echo -e "${YELLOW}[경고] frontend/src/data.json이 없습니다.${NC}"
  echo "  파이프라인을 먼저 실행하세요:"
  echo "    python3 scripts/detect_communities.py"
  echo "    python3 scripts/generate_community_reports.py"
  echo "    python3 scripts/enrich_graph.py"
  exit 1
fi

# node_modules 존재 확인
if [ ! -d "frontend/node_modules" ]; then
  echo -e "${CYAN}[준비] 프론트엔드 의존성 설치 중...${NC}"
  (cd frontend && npm install)
fi

# ─── 종료 시 자식 프로세스 정리 ───

cleanup() {
  echo ""
  echo -e "${YELLOW}[종료] 서버를 중지합니다...${NC}"
  kill $API_PID $FRONTEND_PID 2>/dev/null
  wait $API_PID $FRONTEND_PID 2>/dev/null
  echo -e "${GREEN}[완료] 모든 서버가 종료되었습니다.${NC}"
}
trap cleanup EXIT INT TERM

# ─── API 서버 시작 ───

echo -e "${CYAN}[1/2] 검색 API 서버 시작 (http://localhost:8000)${NC}"
python3 server.py &
API_PID=$!

# API 서버가 준비될 때까지 대기
for i in {1..10}; do
  if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    HEALTH=$(curl -s http://localhost:8000/api/health)
    NODES=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin)['nodes'])" 2>/dev/null || echo "?")
    LINKS=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin)['links'])" 2>/dev/null || echo "?")
    echo -e "${GREEN}  ✓ API 서버 준비 완료 (${NODES}개 노드, ${LINKS}개 링크)${NC}"
    break
  fi
  sleep 1
done

# ─── 프론트엔드 서버 시작 ───

echo -e "${CYAN}[2/2] 프론트엔드 개발 서버 시작${NC}"
(cd frontend && npm run dev) &
FRONTEND_PID=$!

sleep 2
echo ""
echo -e "${GREEN}══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ManseiGraph 실행 중${NC}"
echo ""
echo -e "  프론트엔드:  ${CYAN}http://localhost:5173${NC}"
echo -e "  검색 API:    ${CYAN}http://localhost:8000${NC}"
echo -e "  헬스체크:    ${CYAN}http://localhost:8000/api/health${NC}"
echo ""
echo -e "  ${YELLOW}Ctrl+C${NC}로 종료"
echo -e "${GREEN}══════════════════════════════════════════════${NC}"
echo ""

# 자식 프로세스가 종료될 때까지 대기
wait
