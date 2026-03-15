// 볼록 껍질(convex hull) 계산 - Graham scan
export function convexHull(points: { x: number; y: number }[]): { x: number; y: number }[] {
  if (points.length < 3) return points;
  const sorted = [...points].sort((a, b) => a.x - b.x || a.y - b.y);
  const cross = (o: { x: number; y: number }, a: { x: number; y: number }, b: { x: number; y: number }) =>
    (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);

  const lower: { x: number; y: number }[] = [];
  for (const p of sorted) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0)
      lower.pop();
    lower.push(p);
  }
  const upper: { x: number; y: number }[] = [];
  for (let i = sorted.length - 1; i >= 0; i--) {
    const p = sorted[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0)
      upper.pop();
    upper.push(p);
  }
  upper.pop();
  lower.pop();
  return lower.concat(upper);
}

// 노드 툴팁(tooltip) HTML 생성
export function buildNodeTooltip(
  node: any,
  color: string,
  connections: number,
  typeLabels: Record<string, string>,
): string {
  const desc = node.description || '';
  const truncDesc = desc.length > 80 ? desc.slice(0, 80) + '…' : desc;
  return `<div style="
    background: #fff;
    color: #1a1a1a;
    padding: 0;
    border-radius: 10px;
    font-size: 13px;
    border: 1px solid #e0e0e0;
    box-shadow: none;
    line-height: 1.5;
    min-width: 200px;
    max-width: 300px;
    overflow: hidden;
  ">
    <div style="
      padding: 10px 14px 8px;
      border-bottom: 1px solid #f0f0f0;
      display: flex;
      align-items: center;
      gap: 8px;
    ">
      <span style="
        background: ${color};
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        flex-shrink: 0;
      "></span>
      <div style="flex: 1; min-width: 0;">
        <div style="font-weight: 700; font-size: 14px;">${node.name}</div>
        <div style="font-size: 10px; color: #999; margin-top: 1px; font-weight: 500; letter-spacing: 0.3px; text-transform: uppercase;">
          ${typeLabels[node.type] || node.type}
        </div>
      </div>
    </div>
    ${truncDesc ? `
      <div style="
        padding: 8px 14px;
        font-size: 12px;
        color: #555;
        line-height: 1.6;
        word-break: keep-all;
      ">${truncDesc}</div>
    ` : ''}
    <div style="
      padding: 6px 14px 8px;
      display: flex;
      gap: 6px;
      border-top: 1px solid #f0f0f0;
    ">
      <span style="
        font-size: 10px;
        color: #888;
        background: #f5f5f5;
        padding: 2px 8px;
        border-radius: 8px;
      ">연결 ${connections}</span>
      ${node.communityName ? `<span style="
        font-size: 10px;
        color: ${color};
        background: #f5f5f5;
        padding: 2px 8px;
        border-radius: 8px;
      ">${node.communityName}</span>` : ''}
    </div>
  </div>`;
}

// 퍼지(fuzzy) 검색 매칭 함수
export function fuzzyMatch(text: string, query: string): { match: boolean; score: number } {
  const lower = text.toLowerCase();
  const q = query.toLowerCase();
  // 정확한 포함(exact substring)은 높은 점수
  if (lower.includes(q)) return { match: true, score: 2 };
  // 순차 문자 매칭(sequential char match)
  let qi = 0;
  for (let i = 0; i < lower.length && qi < q.length; i++) {
    if (lower[i] === q[qi]) qi++;
  }
  return { match: qi === q.length, score: qi === q.length ? 1 : 0 };
}
