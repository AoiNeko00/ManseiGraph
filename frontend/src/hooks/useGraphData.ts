import { useMemo, useRef } from 'react';
import graphRawData from '../data.json';
import type { GraphData } from '../types';
import { getRelationLabel } from '../constants';

// 그래프 데이터 처리 훅(graph data processing hook)
export function useGraphData(
  expandedNodes: Set<string>,
  selectedNode: { id: string } | null,
  fgRef: React.RefObject<any>,
) {
  // 전체 데이터에서 이웃(neighbor) 맵 생성
  const neighborMap = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const node of graphRawData.nodes) {
      map.set(node.id, new Set());
    }
    for (const link of graphRawData.links) {
      const src = typeof link.source === 'string' ? link.source : (link.source as any).id;
      const tgt = typeof link.target === 'string' ? link.target : (link.target as any).id;
      map.get(src)?.add(tgt);
      map.get(tgt)?.add(src);
    }
    return map;
  }, []);

  // 표시할 노드 ID 계산(progressive exploration)
  const visibleNodeIds = useMemo(() => {
    const ids = new Set<string>();
    for (const nodeId of expandedNodes) {
      ids.add(nodeId);
      const neighbors = neighborMap.get(nodeId);
      if (neighbors) {
        for (const nId of neighbors) {
          ids.add(nId);
        }
      }
    }
    return ids;
  }, [expandedNodes, neighborMap]);

  // 기존 노드 좌표(position) 캐시
  const nodePositionCache = useRef<Map<string, { x: number; y: number }>>(new Map());

  // 필터링된 그래프 데이터 + 좌표 상속
  const filteredData: GraphData = useMemo(() => {
    if (fgRef.current) {
      const currentNodes = fgRef.current.graphData?.()?.nodes;
      if (currentNodes) {
        for (const n of currentNodes) {
          if (n.x !== undefined && n.y !== undefined) {
            nodePositionCache.current.set(n.id, { x: n.x, y: n.y });
          }
        }
      }
    }

    const nodes = graphRawData.nodes
      .filter((n) => visibleNodeIds.has(n.id))
      .map((n) => {
        const cached = nodePositionCache.current.get(n.id);
        if (cached) return { ...n, x: cached.x, y: cached.y };
        const neighbors = neighborMap.get(n.id);
        if (neighbors) {
          for (const nId of neighbors) {
            const parentPos = nodePositionCache.current.get(nId);
            if (parentPos) {
              const jitter = () => (Math.random() - 0.5) * 30;
              return { ...n, x: parentPos.x + jitter(), y: parentPos.y + jitter() };
            }
          }
        }
        return n;
      });

    const links = graphRawData.links.filter((l) => {
      const src = typeof l.source === 'string' ? l.source : (l.source as any).id;
      const tgt = typeof l.target === 'string' ? l.target : (l.target as any).id;
      return visibleNodeIds.has(src) && visibleNodeIds.has(tgt);
    });

    if (nodes.length === 0 && graphRawData.nodes.length > 0) {
      return { nodes: [graphRawData.nodes[0]], links: [] } as GraphData;
    }
    return { nodes, links } as GraphData;
  }, [visibleNodeIds, neighborMap, fgRef]);

  // 선택된 노드의 연결 정보(connections) — 링크 단위로 생성
  const selectedConnections = useMemo(() => {
    if (!selectedNode) return [];
    return graphRawData.links
      .filter((l) => {
        const src = typeof l.source === 'string' ? l.source : (l.source as any).id;
        const tgt = typeof l.target === 'string' ? l.target : (l.target as any).id;
        return src === selectedNode.id || tgt === selectedNode.id;
      })
      .map((l) => {
        const src = typeof l.source === 'string' ? l.source : (l.source as any).id;
        const tgt = typeof l.target === 'string' ? l.target : (l.target as any).id;
        const otherId = src === selectedNode.id ? tgt : src;
        const otherNode = graphRawData.nodes.find((n) => n.id === otherId);
        return {
          id: otherId,
          name: otherNode?.name ?? otherId,
          type: otherNode?.type ?? 'concept',
          relation: getRelationLabel(l.relation),
        };
      });
  }, [selectedNode]);

  return {
    neighborMap,
    visibleNodeIds,
    filteredData,
    selectedConnections,
    nodePositionCache,
  };
}
