import { useCallback, useMemo } from 'react';
import type { GraphNode, GraphLink } from '../types';
import {
  COMMUNITY_COLORS,
  COMMUNITY_HULL_COLORS,
  FALLBACK_COLOR,
  RELATION_DASH,
} from '../constants';
import { convexHull } from '../utils';

// 점선(dashed) 테두리가 필요한 타입
const DASHED_TYPES = new Set(['location', 'concept']);

interface UseCanvasRenderersDeps {
  selectedNode: GraphNode | null;
  hoveredNode: GraphNode | null;
  hoveredConnectionId: string | null;
  hoveredLink: GraphLink | null;
  expandedNodes: Set<string>;
  activeCommunities: Set<string>;
  activeTypes: Set<string>;
  twoHopNeighbors: Set<string> | null;
  isLinkConnectedToSelected: (link: any) => boolean;
  activatedNodes?: Set<string>;
  fgRef: React.RefObject<any>;
}

export function useCanvasRenderers(deps: UseCanvasRenderersDeps) {
  const {
    selectedNode,
    hoveredNode,
    hoveredConnectionId,
    hoveredLink,
    expandedNodes,
    activeCommunities,
    activeTypes,
    twoHopNeighbors,
    isLinkConnectedToSelected,
    activatedNodes,
    fgRef,
  } = deps;

  // 노드의 커뮤니티 색상 반환(community color)
  const getNodeColor = useCallback((node: any): string => {
    return COMMUNITY_COLORS[node.communityId] || FALLBACK_COLOR;
  }, []);

  // 노드 반지름(radius) 계산 함수 — paintNode와 동일 공식
  const getNodeRadius = useCallback((node: any) => {
    return Math.sqrt(Math.max(node.degree || 1, 1)) * 2.2 + 3;
  }, []);

  // 노드 도형(shape) 경로 생성 — type별 분리
  const drawNodeShape = useCallback(
    (ctx: CanvasRenderingContext2D, x: number, y: number, r: number, type: string) => {
      ctx.beginPath();
      switch (type) {
        case 'organization': {
          // 육각형(hexagon)
          for (let i = 0; i < 6; i++) {
            const angle = (Math.PI / 3) * i - Math.PI / 2;
            const px = x + r * Math.cos(angle);
            const py = y + r * Math.sin(angle);
            i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
          }
          ctx.closePath();
          break;
        }
        case 'event': {
          // 다이아몬드(diamond)
          ctx.moveTo(x, y - r);
          ctx.lineTo(x + r, y);
          ctx.lineTo(x, y + r);
          ctx.lineTo(x - r, y);
          ctx.closePath();
          break;
        }
        case 'location': {
          // 둥근 사각형(rounded rect)
          const half = r * 0.85;
          const cr = r * 0.25;
          ctx.moveTo(x - half + cr, y - half);
          ctx.arcTo(x + half, y - half, x + half, y + half, cr);
          ctx.arcTo(x + half, y + half, x - half, y + half, cr);
          ctx.arcTo(x - half, y + half, x - half, y - half, cr);
          ctx.arcTo(x - half, y - half, x + half, y - half, cr);
          ctx.closePath();
          break;
        }
        case 'concept': {
          // 삼각형(triangle)
          const h = r * 1.15;
          ctx.moveTo(x, y - h);
          ctx.lineTo(x + r, y + h * 0.5);
          ctx.lineTo(x - r, y + h * 0.5);
          ctx.closePath();
          break;
        }
        default: {
          // person 및 기타 — 원(circle)
          ctx.arc(x, y, r, 0, Math.PI * 2);
          break;
        }
      }
    },
    [],
  );

  // 커뮤니티별 노드 그룹핑 — paintBefore 의존성용 (실제 렌더링은 최신 좌표 사용)
  const communityGroups = useMemo(() => {
    // paintBefore의 deps 안정화를 위한 더미(dummy) — 실제 그룹은 fgRef에서 계산
    return new Map<string, { x: number; y: number }[]>();
  }, []);

  // 캔버스 전처리(pre-paint): 커뮤니티 헐(hull) 그리기
  const paintBefore = useCallback(
    (ctx: CanvasRenderingContext2D, globalScale: number) => {
      // 현재 노드들의 최신 좌표로 커뮤니티 그룹 재계산
      const currentNodes = fgRef.current?.graphData?.()?.nodes;
      if (!currentNodes) return;

      const groups = new Map<string, { x: number; y: number }[]>();
      for (const n of currentNodes) {
        if (n.communityId && n.x !== undefined && n.y !== undefined) {
          if (!groups.has(n.communityId)) groups.set(n.communityId, []);
          groups.get(n.communityId)!.push({ x: n.x, y: n.y });
        }
      }

      for (const [communityId, points] of groups) {
        if (points.length < 3) continue;
        const hull = convexHull(points);
        if (hull.length < 3) continue;

        const padding = 30 / globalScale;
        // 중심(centroid) 계산
        const cx = hull.reduce((s, p) => s + p.x, 0) / hull.length;
        const cy = hull.reduce((s, p) => s + p.y, 0) / hull.length;

        ctx.beginPath();
        const expanded = hull.map((p) => {
          const dx = p.x - cx;
          const dy = p.y - cy;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const scale = (dist + padding) / (dist || 1);
          return { x: cx + dx * scale, y: cy + dy * scale };
        });

        // 부드러운 곡선(smooth curve)으로 헐 그리기
        ctx.moveTo(expanded[0].x, expanded[0].y);
        for (let i = 0; i < expanded.length; i++) {
          const curr = expanded[i];
          const next = expanded[(i + 1) % expanded.length];
          const midX = (curr.x + next.x) / 2;
          const midY = (curr.y + next.y) / 2;
          ctx.quadraticCurveTo(curr.x, curr.y, midX, midY);
        }
        ctx.closePath();

        // 활성화된 커뮤니티 여부 판별 (검색 결과 노드의 소속 커뮤니티)
        const isActivatedCommunity = activatedNodes && activatedNodes.size > 0 &&
          currentNodes.some((n: any) => n.communityId === communityId && activatedNodes.has(n.id));

        if (isActivatedCommunity) {
          // 활성화 커뮤니티: 호박색(amber) 강조
          ctx.fillStyle = 'rgba(245, 158, 11, 0.12)';
          ctx.fill();
          ctx.strokeStyle = '#f59e0b';
          ctx.lineWidth = 2.5 / globalScale;
          ctx.stroke();
        } else {
          ctx.fillStyle = COMMUNITY_HULL_COLORS[communityId] || 'rgba(180,180,180,0.06)';
          ctx.fill();
          ctx.strokeStyle = (COMMUNITY_COLORS[communityId] || '#ccc') + '30';
          ctx.lineWidth = 1.5 / globalScale;
          ctx.stroke();
        }
      }
    },
    [communityGroups, fgRef, activatedNodes],
  );

  // 캔버스에 노드 커스텀 렌더링 — 이중 인코딩(dual encoding)
  const paintNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const radius = Math.sqrt(Math.max(node.degree || 1, 1)) * 2.2 + 3;
      const color = getNodeColor(node);
      const isSelected = selectedNode?.id === node.id;
      const isHovered = hoveredNode?.id === node.id || hoveredConnectionId === node.id;
      const isExpanded = expandedNodes.has(node.id);
      const nodeType: string = node.type || 'person';

      // 필터(filter) 적용: 커뮤니티 또는 타입에 해당하지 않으면 dim 처리
      const isDimmedByCommunity = !activeCommunities.has(node.communityId);
      const isDimmedByType = !activeTypes.has(nodeType);
      // 2-hop 딥 포커스(deep focus): 선택 노드의 2-hop 밖이면 dim
      const isDimmedByFocus = twoHopNeighbors !== null && !twoHopNeighbors.has(node.id);
      const isDimmed = isDimmedByCommunity || isDimmedByType || isDimmedByFocus;

      // degree 기반 테두리(border) 두께 + 글로우(glow) 강도
      const degree = node.degree || 0;
      const borderWidth = 1 + (degree / 29) * 2; // 1px ~ 3px
      const glowRadius = degree >= 10 ? 6 : degree >= 5 ? 3 : 0;
      const glowAlpha = Math.min(degree / 29, 0.4);

      const x = node.x ?? 0;
      const y = node.y ?? 0;

      // 호버(hover) 시 반지름 확대
      const drawRadius = isHovered ? radius * 1.25 : radius;

      ctx.save();

      // 필터 dim 적용(filter dim)
      if (isDimmed) {
        ctx.globalAlpha = 0.1;
      }

      // degree 글로우(glow) — 고연결(high-degree) 노드
      if (glowRadius > 0) {
        ctx.shadowColor = color;
        ctx.shadowBlur = glowRadius * (isHovered ? 1.5 : 1);
        ctx.globalAlpha = glowAlpha;
        drawNodeShape(ctx, x, y, drawRadius + 2, nodeType);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.globalAlpha = 1.0;
      }

      // GraphRAG 검색 결과 활성화(activated) 노드 하이라이트
      const isActivated = activatedNodes && activatedNodes.size > 0 && activatedNodes.has(node.id);
      if (isActivated) {
        // 외곽 펄스(pulse) 링
        drawNodeShape(ctx, x, y, drawRadius + 6 / globalScale, nodeType);
        ctx.fillStyle = '#f59e0b40'; // 호박색(amber) 반투명
        ctx.fill();
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 2 / globalScale;
        drawNodeShape(ctx, x, y, drawRadius + 6 / globalScale, nodeType);
        ctx.stroke();
      }

      // 선택된 노드 글로우(glow) 효과
      if (isSelected) {
        drawNodeShape(ctx, x, y, drawRadius + 4 / globalScale, nodeType);
        ctx.fillStyle = color + '40';
        ctx.fill();
      }

      // 노드 본체(body) 채우기
      drawNodeShape(ctx, x, y, drawRadius, nodeType);
      ctx.fillStyle = color;
      ctx.globalAlpha = isHovered ? 1.0 : isSelected ? 1.0 : 0.85;
      ctx.fill();

      // 호버(hover) 시 그림자(shadow) 효과
      if (isHovered) {
        ctx.shadowColor = color;
        ctx.shadowBlur = 8;
      }

      // 테두리(border) — type에 따라 실선/점선 분기
      const isDashed = DASHED_TYPES.has(nodeType);
      if (isDashed) {
        ctx.setLineDash([3 / globalScale, 2 / globalScale]);
      }

      if (isSelected) {
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 2.5 / globalScale;
      } else {
        ctx.strokeStyle = color + 'AA';
        ctx.lineWidth = borderWidth / globalScale;
      }
      drawNodeShape(ctx, x, y, drawRadius, nodeType);
      ctx.stroke();

      if (isDashed) {
        ctx.setLineDash([]);
      }
      ctx.shadowBlur = 0;
      ctx.globalAlpha = 1.0;

      // 확장(expanded) 상태 — 내부 도트(inner dot)
      if (isExpanded) {
        ctx.beginPath();
        ctx.arc(x, y, 2, 0, Math.PI * 2);
        ctx.fillStyle = '#333';
        ctx.fill();
      }

      // 노드 하단 라벨(label) — 커뮤니티/타입 필터 dim에서만 숨김, 포커스 dim은 연하게 표시
      if (!isDimmedByCommunity && !isDimmedByType) {
        const fontSize = Math.max(10 / globalScale, 1.8);
        ctx.font = `500 ${fontSize}px 'Pretendard', -apple-system, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        const labelY = y + drawRadius + 2 / globalScale;
        ctx.globalAlpha = isDimmedByFocus ? 0.3 : 1.0;
        ctx.strokeStyle = 'rgba(252,252,252,0.85)';
        ctx.lineWidth = 3 / globalScale;
        ctx.lineJoin = 'round';
        ctx.strokeText(node.name, x, labelY);
        ctx.fillStyle = '#333';
        ctx.fillText(node.name, x, labelY);
      }

      ctx.restore();
    },
    [selectedNode, hoveredNode, hoveredConnectionId, expandedNodes, getNodeColor, drawNodeShape, activeCommunities, activeTypes, twoHopNeighbors, activatedNodes],
  );

  // 엣지(link) 커스텀 렌더링 — relation별 색상 + dash 패턴
  const paintLink = useCallback(
    (link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const src = typeof link.source === 'object' ? link.source : null;
      const tgt = typeof link.target === 'object' ? link.target : null;
      if (!src || !tgt || src.x == null || tgt.x == null) return;

      const relation: string = link.relation || 'related_to';
      const dashPattern = RELATION_DASH[relation] || RELATION_DASH.related_to;

      const isConnected = isLinkConnectedToSelected(link);
      const isHovered = hoveredLink &&
        ((typeof hoveredLink.source === 'object' ? hoveredLink.source?.id : hoveredLink.source) ===
          (typeof link.source === 'object' ? link.source?.id : link.source)) &&
        ((typeof hoveredLink.target === 'object' ? hoveredLink.target?.id : hoveredLink.target) ===
          (typeof link.target === 'object' ? link.target?.id : link.target));

      // 호버(hover) 노드에 연결된 엣지 강조
      const srcId = typeof link.source === 'object' ? link.source?.id : link.source;
      const tgtId = typeof link.target === 'object' ? link.target?.id : link.target;
      const hoveredId = hoveredNode?.id || hoveredConnectionId;
      const isConnectedToHovered = hoveredId && (srcId === hoveredId || tgtId === hoveredId);

      // 커뮤니티/타입/딥포커스 필터(filter) dim 계산
      const srcType: string = src?.type || 'person';
      const tgtType: string = tgt?.type || 'person';
      const srcDimmed = !activeCommunities.has(src?.communityId)
        || !activeTypes.has(srcType)
        || (twoHopNeighbors !== null && !twoHopNeighbors.has(srcId));
      const tgtDimmed = !activeCommunities.has(tgt?.communityId)
        || !activeTypes.has(tgtType)
        || (twoHopNeighbors !== null && !twoHopNeighbors.has(tgtId));
      const linkDimmed = srcDimmed && tgtDimmed;
      const linkPartialDim = srcDimmed || tgtDimmed;

      // strength(관계 강도, 1~10)를 너비에 반영: 강한 관계일수록 두꺼운 선
      const strength = (link as GraphLink).strength ?? 5;
      const baseWidth = (strength / 10) * 0.6 + 0.2; // 최소 0.26, 최대 0.8
      let opacity: number;
      let width: number;

      if (linkDimmed) {
        opacity = 0.05;
        width = baseWidth;
      } else if (isHovered) {
        opacity = 1.0;
        width = Math.min(baseWidth * 2.5, 1.2);
      } else if (isConnectedToHovered) {
        opacity = 0.7;
        width = Math.min(baseWidth * 2, 1.0);
      } else if (isConnected) {
        opacity = linkPartialDim ? 0.3 : 0.8;
        width = Math.min(baseWidth * 2, 1.0);
      } else {
        opacity = linkPartialDim ? 0.1 : 0.35;
        width = baseWidth;
      }

      // 엣지(edge) 색상: 기본 진한 슬레이트, 선택/호버 시 진청색
      let strokeColor: string;
      if (isHovered || isConnected) {
        strokeColor = '#1a3a5c'; // 진청색(deep blue) — 선택/호버 강조
      } else {
        strokeColor = '#4a5568'; // 진한 슬레이트 그레이(slate gray)
      }

      ctx.save();
      ctx.globalAlpha = opacity;
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = width / globalScale;

      // 대시(dash) 패턴 적용 (globalScale 보정)
      if (dashPattern.length > 0) {
        ctx.setLineDash(dashPattern.map(d => d / globalScale));
      }

      // 호버(hover) 시 글로우(glow) 효과
      if (isHovered) {
        ctx.shadowColor = strokeColor;
        ctx.shadowBlur = 4;
      }

      ctx.beginPath();
      ctx.moveTo(src.x, src.y);
      ctx.lineTo(tgt.x, tgt.y);
      ctx.stroke();

      ctx.restore();
    },
    [selectedNode, hoveredNode, hoveredConnectionId, hoveredLink, isLinkConnectedToSelected, activeCommunities, activeTypes, twoHopNeighbors],
  );

  return { paintNode, paintLink, paintBefore, getNodeColor, getNodeRadius, drawNodeShape };
}
