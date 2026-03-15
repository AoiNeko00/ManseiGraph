import { useCallback } from 'react';
import graphRawData from '../data.json';
import type { GraphNode, GraphLink } from '../types';
import { SEED_NODE_ID } from '../constants';

interface UseGraphControlsDeps {
  fgRef: React.RefObject<any>;
  selectedNode: GraphNode | null;
  expandedNodes: Set<string>;
  centerTimerRef: React.MutableRefObject<ReturnType<typeof setInterval> | null>;
  clickTimerRef: React.MutableRefObject<ReturnType<typeof setTimeout> | null>;
  neighborMap: Map<string, Set<string>>;
  setSelectedNode: (node: GraphNode | null) => void;
  setSelectedLink: (link: GraphLink | null) => void;
  setExpandedNodes: React.Dispatch<React.SetStateAction<Set<string>>>;
  setActiveCommunities: React.Dispatch<React.SetStateAction<Set<string>>>;
  setActiveTypes: React.Dispatch<React.SetStateAction<Set<string>>>;
}

// 싱글/더블클릭 구분 지연(delay) 시간
const CLICK_DELAY = 250; // ms

export function useGraphControls(deps: UseGraphControlsDeps) {
  const {
    fgRef,
    selectedNode,
    expandedNodes,
    centerTimerRef,
    clickTimerRef,
    neighborMap: _neighborMap,
    setSelectedNode,
    setSelectedLink,
    setExpandedNodes,
    setActiveCommunities,
    setActiveTypes,
  } = deps;

  // 노드 클릭 핸들러: 확장 + 2-hop 지능형 줌(intelligent zoom) + 정밀 포커싱(precision focus)
  const handleNodeClick = useCallback(
    (node: any) => {
      if (!fgRef.current) return;
      const fg = fgRef.current;

      // 검색 등 외부 소스에서 호출된 경우, d3 시뮬레이션의 실제 노드 객체에서 좌표 조회
      let liveNode = node;
      if (node.x === undefined || node.y === undefined) {
        const currentNodes = fg.graphData?.()?.nodes;
        const found = currentNodes?.find((n: any) => n.id === node.id);
        if (found) liveNode = found;
      }

      // 1. 클릭 시점의 노드 좌표 캡처 (물리 엔진 재가열 전)
      const targetX = liveNode.x as number | undefined;
      const targetY = liveNode.y as number | undefined;

      // 2. 상태 변경
      setSelectedNode(node as GraphNode);
      setSelectedLink(null);
      // 이미 확장된 노드면 Set을 새로 만들지 않음 (불필요한 filteredData 재계산 방지)
      setExpandedNodes((prev) => {
        if (prev.has(node.id)) return prev;
        const next = new Set(prev);
        next.add(node.id);
        return next;
      });

      // 3. 기존 타이머 정리(cleanup)
      if (centerTimerRef.current) {
        clearInterval(centerTimerRef.current);
        centerTimerRef.current = null;
      }

      // 4. 좌표가 있으면 줌 + 센터 이동
      if (targetX !== undefined && targetY !== undefined) {
        const currentZoom = fg.zoom() ?? 1;
        const ZOOM_DURATION = 800;
        const MIN_ZOOM = 3;
        const targetZoom = Math.max(currentZoom, MIN_ZOOM);

        // 사이드 패널(380px) 오프셋 보정
        const SIDE_PANEL_WIDTH = 380;
        const panelHalfPx = SIDE_PANEL_WIDTH / 2;

        fg.zoom(targetZoom, ZOOM_DURATION);
        fg.centerAt(targetX + panelHalfPx / targetZoom, targetY, ZOOM_DURATION);
      }

    },
    [fgRef, centerTimerRef, setSelectedNode, setSelectedLink, setExpandedNodes],
  );

  // 노드 더블클릭 핸들러: 확장된 노드 축소(collapse)
  const handleNodeDoubleClick = useCallback(
    (node: any) => {
      if (node.id === SEED_NODE_ID) return; // 시드 노드 제외
      if (!expandedNodes.has(node.id)) return; // 미확장 노드 무시

      setExpandedNodes((prev) => {
        const next = new Set(prev);
        next.delete(node.id);
        return next;
      });
    },
    [expandedNodes, setExpandedNodes],
  );

  // 싱글/더블클릭 구분 핸들러 — 타이머 기반
  const handleNodeClickWithTimer = useCallback(
    (node: any) => {
      if (clickTimerRef.current) {
        // 더블클릭: 타이머 취소 + 더블클릭 실행
        clearTimeout(clickTimerRef.current);
        clickTimerRef.current = null;
        handleNodeDoubleClick(node);
      } else {
        // 싱글클릭: 지연 실행
        clickTimerRef.current = setTimeout(() => {
          clickTimerRef.current = null;
          handleNodeClick(node);
        }, CLICK_DELAY);
      }
    },
    [handleNodeClick, handleNodeDoubleClick, clickTimerRef],
  );

  // 엣지 클릭 핸들러: sourceContext 표시
  const handleLinkClick = useCallback((link: any) => {
    setSelectedLink(link as GraphLink);
  }, [setSelectedLink]);

  // 전체 뷰로 리셋
  const handleReset = useCallback(() => {
    setExpandedNodes(new Set(graphRawData.nodes.map((n) => n.id)));
    setSelectedNode(null);
    setSelectedLink(null);
    setActiveCommunities(new Set());
    setTimeout(() => {
      if (fgRef.current) fgRef.current.zoomToFit(600, 60);
    }, 100);
  }, [fgRef, setExpandedNodes, setSelectedNode, setSelectedLink, setActiveCommunities]);

  // 전체 맞춤(fit to view)
  const handleFitView = useCallback(() => {
    if (fgRef.current) fgRef.current.zoomToFit(600, 50);
  }, [fgRef]);

  // 확대(zoom in)
  const handleZoomIn = useCallback(() => {
    if (fgRef.current) {
      const currentZoom = fgRef.current.zoom();
      fgRef.current.zoom(currentZoom * 1.5, 400);
    }
  }, [fgRef]);

  // 축소(zoom out)
  const handleZoomOut = useCallback(() => {
    if (fgRef.current) {
      const currentZoom = fgRef.current.zoom();
      fgRef.current.zoom(currentZoom / 1.5, 400);
    }
  }, [fgRef]);

  // 선택 노드로 이동
  const handleGoToSelected = useCallback(() => {
    if (fgRef.current && selectedNode && selectedNode.x !== undefined && selectedNode.y !== undefined) {
      fgRef.current.centerAt(selectedNode.x, selectedNode.y, 1200);
    }
  }, [fgRef, selectedNode]);

  // 커뮤니티 필터 토글 핸들러 — 다중 선택(multi-select)
  const handleCommunityToggle = useCallback((id: string) => {
    setActiveCommunities((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        // 최소 1개는 활성 유지
        if (next.size > 1) next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, [setActiveCommunities]);

  // 타입 필터 토글 핸들러
  const handleTypeToggle = useCallback((type: string) => {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        // 최소 1개는 활성 유지
        if (next.size > 1) next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  }, [setActiveTypes]);

  return {
    handleNodeClick,
    handleNodeClickWithTimer,
    handleLinkClick,
    handleReset,
    handleFitView,
    handleZoomIn,
    handleZoomOut,
    handleGoToSelected,
    handleCommunityToggle,
    handleTypeToggle,
  };
}
