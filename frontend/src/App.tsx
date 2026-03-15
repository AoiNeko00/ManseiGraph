import { useRef, useState, useMemo, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { forceCollide } from 'd3-force-3d';
import graphRawData from './data.json';
import { Plus, Minus, Maximize2, Navigation, RotateCcw } from 'lucide-react';
import './App.css';

import type { GraphNode, GraphLink } from './types';
import {
  TYPE_LABELS,
  COMMUNITY_COLORS,
  RELATION_COLORS,
} from './constants';
import { fuzzyMatch, buildNodeTooltip } from './utils';
import { useGraphData } from './hooks/useGraphData';
import { useCanvasRenderers } from './hooks/useCanvasRenderers';
import { useGraphControls } from './hooks/useGraphControls';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { SidePanel } from './components/SidePanel';
import { ContextPanel } from './components/ContextPanel';
import { SearchModal } from './components/SearchModal';
import { Legend } from './components/Legend';
import { QueryPanel } from './components/QueryPanel';

function App() {
  const fgRef = useRef<any>(null);
  const centerTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(
    new Set(graphRawData.nodes.map((n) => n.id))
  );
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedLink, setSelectedLink] = useState<GraphLink | null>(null);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [hoveredLink, setHoveredLink] = useState<GraphLink | null>(null);
  const [hoveredConnectionId, setHoveredConnectionId] = useState<string | null>(null);
  // 검색 모달(search modal) 상태
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchSelectedIndex, setSearchSelectedIndex] = useState(0);
  const searchInputRef = useRef<HTMLInputElement>(null);
  // 커뮤니티 필터(community filter) 상태 — 전체 활성으로 초기화
  const [activeCommunities, setActiveCommunities] = useState<Set<string>>(
    new Set(Object.keys(COMMUNITY_COLORS))
  );
  // 타입 필터(type filter) 상태
  const [activeTypes, setActiveTypes] = useState<Set<string>>(
    new Set(['person', 'organization', 'event', 'location', 'concept'])
  );

  // 그래프 로딩 상태(loading state)
  const [isGraphReady, setIsGraphReady] = useState(false);
  const [isLoadingVisible, setIsLoadingVisible] = useState(true);
  // 싱글/더블클릭 구분 타이머
  const clickTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 엣지 클릭 고정(pinned) 상태 — 호버 해제로 패널이 닫히지 않도록
  const linkClickedRef = useRef(false);
  const [dimensions, setDimensions] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  });

  // 그래프 데이터 훅(hook)
  const { neighborMap, filteredData, selectedConnections } = useGraphData(
    expandedNodes,
    selectedNode,
    fgRef,
  );

  // 윈도우 리사이즈(resize)
  useEffect(() => {
    const handleResize = () => {
      setDimensions({ width: window.innerWidth, height: window.innerHeight });
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // 컴포넌트 언마운트 시 타이머/애니메이션 정리
  useEffect(() => {
    return () => {
      if (centerTimerRef.current) clearInterval(centerTimerRef.current);
      if (clickTimerRef.current) clearTimeout(clickTimerRef.current);
    };
  }, []);

  // 초기 카메라: 전체 그래프가 화면에 들어오도록 zoomToFit
  const initializedRef = useRef(false);
  useEffect(() => {
    if (fgRef.current && !initializedRef.current) {
      initializedRef.current = true;
      setTimeout(() => {
        if (fgRef.current) {
          fgRef.current.zoomToFit(800, 60);
        }
      }, 500);
    }
  }, [filteredData.nodes]);

  // GraphRAG 검색으로 활성화된 노드(activated nodes) 상태
  const [activatedNodes, setActivatedNodes] = useState<Set<string>>(new Set());

  // 선택 노드 기준 2-hop 이웃 집합(deep focus)
  const twoHopNeighbors = useMemo(() => {
    if (!selectedNode) return null;
    const set = new Set<string>();
    set.add(selectedNode.id);
    // 1-hop
    const hop1 = neighborMap.get(selectedNode.id);
    if (hop1) {
      for (const id of hop1) {
        set.add(id);
        // 2-hop
        const hop2 = neighborMap.get(id);
        if (hop2) {
          for (const id2 of hop2) set.add(id2);
        }
      }
    }
    return set;
  }, [selectedNode, neighborMap]);

  // 링크가 선택된 노드에 연결되어 있는지 확인
  const isLinkConnectedToSelected = useMemo(() => {
    return (link: any) => {
      if (!selectedNode) return false;
      const src = typeof link.source === 'string' ? link.source : link.source?.id;
      const tgt = typeof link.target === 'string' ? link.target : link.target?.id;
      return src === selectedNode.id || tgt === selectedNode.id;
    };
  }, [selectedNode]);

  // 캔버스 렌더러(canvas renderers)
  const { paintNode, paintLink, paintBefore, getNodeColor, getNodeRadius } =
    useCanvasRenderers({
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
    });

  // d3 물리 엔진(physics) 초기 설정 — filteredData 변경 시 force만 재설정, reheat는 하지 않음
  const physicsInitialized = useRef(false);
  useEffect(() => {
    if (fgRef.current) {
      const fg = fgRef.current;
      fg.d3Force('charge')?.strength(-800).distanceMax(1200).distanceMin(30);
      fg.d3Force('link')?.distance(120).strength(0.4);
      fg.d3Force('center')?.strength(0.02);
      fg.d3Force('collide', forceCollide()
        .radius((node: any) => getNodeRadius(node) + 6)
        .strength(0.8)
        .iterations(3)
      );
      // 최초 1회만 reheat — 이후 클릭 시 노드 재배치 방지
      if (!physicsInitialized.current) {
        physicsInitialized.current = true;
        fg.d3ReheatSimulation?.();
      }
    }
  }, [filteredData, getNodeRadius]);

  // 그래프 컨트롤(controls) 핸들러
  const {
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
  } = useGraphControls({
    fgRef,
    selectedNode,
    expandedNodes,
    centerTimerRef,
    clickTimerRef,
    neighborMap,
    setSelectedNode,
    setSelectedLink,
    setExpandedNodes,
    setActiveCommunities,
    setActiveTypes,
  });

  // 검색 결과(search results) 계산
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    return graphRawData.nodes
      .map((n) => {
        const nameMatch = fuzzyMatch(n.name, searchQuery);
        const descMatch = fuzzyMatch(n.description, searchQuery);
        const bestScore = Math.max(nameMatch.score, descMatch.score);
        return { node: n, score: bestScore, match: nameMatch.match || descMatch.match };
      })
      .filter((r) => r.match)
      .sort((a, b) => b.score - a.score)
      .slice(0, 8)
      .map((r) => r.node);
  }, [searchQuery]);

  // 검색 모달 열릴 때 input 포커스
  useEffect(() => {
    if (isSearchOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    }
  }, [isSearchOpen]);

  // 로딩 오버레이 fade-out 후 DOM 제거
  useEffect(() => {
    if (isGraphReady) {
      const timer = setTimeout(() => setIsLoadingVisible(false), 700);
      return () => clearTimeout(timer);
    }
  }, [isGraphReady]);

  // 키보드 단축키(keyboard shortcuts)
  useKeyboardShortcuts({
    isSearchOpen,
    searchResults: searchResults as GraphNode[],
    searchSelectedIndex,
    selectedLink,
    selectedNode,
    setIsSearchOpen,
    setSearchQuery,
    setSearchSelectedIndex,
    setSelectedLink,
    setSelectedNode,
    setExpandedNodes,
    handleNodeClick,
    handleFitView,
    handleReset,
    handleZoomIn,
    handleZoomOut,
  });

  // 사이드바 탭(tab) 상태
  const [activeTab, setActiveTab] = useState<'reasoning' | 'insight' | 'community' | 'claims'>('reasoning');

  return (
    <div className="app-container">
      {/* 한지 질감 배경(hanji texture) */}
      <div className="hanji-texture" />

      {/* 상단 헤더(header) */}
      <header className="app-header">
        <h1 className="app-title">
          <span className="title-accent">E</span>xplainable
          {' '}
          <span className="title-accent">G</span>raph
          <span className="title-accent">RAG</span>
        </h1>
        <p className="app-subtitle">한국 독립운동 지식 그래프 · ManseiGraph</p>
        <div className="header-stats">
          <span>{filteredData.nodes.length} / {graphRawData.nodes.length} 노드</span>
          <span className="stat-divider">·</span>
          <span>{filteredData.links.length} 연결</span>
        </div>
      </header>

      {/* 통합 범례(unified legend) 패널 */}
      <Legend
        activeCommunities={activeCommunities}
        activeTypes={activeTypes}
        handleCommunityToggle={handleCommunityToggle}
        handleTypeToggle={handleTypeToggle}
      />

      {/* 네비게이션 바(navigation bar) */}
      <div className={`nav-bar ${selectedLink && (selectedLink as any).sourceContext ? 'nav-bar-raised' : ''}`}>
        <button onClick={handleZoomIn} className="nav-btn" title="확대">
          <Plus size={18} />
        </button>
        <button onClick={handleZoomOut} className="nav-btn" title="축소">
          <Minus size={18} />
        </button>
        <div className="nav-divider" />
        <button onClick={handleFitView} className="nav-btn" title="전체보기">
          <Maximize2 size={18} />
        </button>
        <button
          onClick={handleGoToSelected}
          className={`nav-btn ${!selectedNode ? 'disabled' : ''}`}
          title={selectedNode ? `${selectedNode.name}(으)로 이동` : '노드를 먼저 선택하세요'}
          disabled={!selectedNode}
        >
          <Navigation size={18} />
        </button>
        <div className="nav-divider" />
        <button onClick={handleReset} className="nav-btn" title="초기화">
          <RotateCcw size={16} />
        </button>
      </div>

      {/* 그래프 캔버스(canvas) */}
      <ForceGraph2D
        ref={fgRef}
        graphData={filteredData}
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="rgba(0,0,0,0)"
        nodeCanvasObject={paintNode}
        onRenderFramePre={paintBefore}
        nodeLabel={(node: any) =>
          buildNodeTooltip(node, getNodeColor(node), neighborMap.get(node.id)?.size || 0, TYPE_LABELS)
        }
        linkCanvasObject={paintLink}
        linkCanvasObjectMode={() => 'replace' as const}
        linkDirectionalParticles={(link: any) =>
          isLinkConnectedToSelected(link) ? 3 : 0
        }
        linkDirectionalParticleWidth={2.5}
        linkDirectionalParticleSpeed={0.005}
        linkDirectionalParticleColor={(link: any) => {
          const relation: string = link.relation || 'related_to';
          return (RELATION_COLORS[relation] || RELATION_COLORS.related_to) + 'AA';
        }}
        linkHoverPrecision={8}
        onNodeHover={(node: any) => setHoveredNode(node as GraphNode | null)}
        onLinkHover={(link: any) => {
          setHoveredLink(link as GraphLink | null);
          // 클릭으로 고정된 엣지가 없을 때만 호버로 패널 제어
          if (!linkClickedRef.current) {
            if (selectedNode && link) {
              const src = typeof link.source === 'object' ? link.source?.id : link.source;
              const tgt = typeof link.target === 'object' ? link.target?.id : link.target;
              if (src === selectedNode.id || tgt === selectedNode.id) {
                setSelectedLink(link as GraphLink);
              }
            } else if (selectedNode && !link) {
              setSelectedLink(null);
            }
          }
        }}
        onNodeClick={(node: any) => {
          linkClickedRef.current = false;
          setSelectedLink(null);
          handleNodeClickWithTimer(node);
        }}
        onLinkClick={(link: any) => {
          linkClickedRef.current = true;
          handleLinkClick(link);
        }}
        onBackgroundClick={() => {
          setSelectedNode(null);
          setSelectedLink(null);
          linkClickedRef.current = false;
        }}
        cooldownTicks={200}
        enableNodeDrag={true}
        minZoom={0.3}
        maxZoom={12}
        d3AlphaDecay={0.05}
        d3AlphaMin={0.005}
        d3VelocityDecay={0.4}
        warmupTicks={50}
        onEngineStop={() => {
          if (!isGraphReady) {
            setIsGraphReady(true);
            if (fgRef.current) fgRef.current.zoomToFit(800, 60);
          }
        }}
      />

      {/* 사이드 패널 - GraphRAG 상세 정보 */}
      <SidePanel
        selectedNode={selectedNode}
        hoveredNode={hoveredNode}
        hoveredConnectionId={hoveredConnectionId}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        handleNodeClick={handleNodeClick}
        setSelectedNode={setSelectedNode}
        setHoveredConnectionId={setHoveredConnectionId}
        getNodeColor={getNodeColor}
        selectedConnections={selectedConnections}
      />

      {/* 엣지 클릭 시 연결 근거(description + sourceContext) 표시 패널 */}
      <ContextPanel
        selectedLink={selectedLink}
        setSelectedLink={setSelectedLink}
        onClose={() => { linkClickedRef.current = false; }}
      />

      {/* 로딩 오버레이(loading overlay) */}
      {isLoadingVisible && (
        <div className={`loading-overlay ${isGraphReady ? 'loading-done' : ''}`}>
          <div className="loading-content">
            <div className="loading-spinner" />
            <h2 className="loading-title">
              <span className="title-accent">E</span>xplainable{' '}
              <span className="title-accent">G</span>raph
              <span className="title-accent">RAG</span>
            </h2>
            <p className="loading-text">독립운동의 기억을 구성하는 중...</p>
          </div>
        </div>
      )}

      {/* 안내 문구(hint) */}
      {!selectedNode && !selectedLink && !isSearchOpen && (
        <div className="hint">
          노드를 클릭하여 네트워크를 탐색하고, 선(엣지)을 클릭하여 원본 발췌문을 확인하세요
          <span className="hint-shortcut">⌘K 검색</span>
        </div>
      )}

      {/* GraphRAG 질의(query) 패널 */}
      <QueryPanel
        onSearchResult={(result) => {
          setActivatedNodes(new Set(result.activated_nodes || []));
        }}
        onClearHighlight={() => setActivatedNodes(new Set())}
        onNodeNavigate={(nodeId) => {
          const node = graphRawData.nodes.find(n => n.id === nodeId);
          if (node) handleNodeClick(node);
        }}
      />

      {/* Quick Search 모달(search modal) — Cmd+K */}
      <SearchModal
        isSearchOpen={isSearchOpen}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        searchResults={searchResults as GraphNode[]}
        searchSelectedIndex={searchSelectedIndex}
        setSearchSelectedIndex={setSearchSelectedIndex}
        handleNodeClick={handleNodeClick}
        setIsSearchOpen={setIsSearchOpen}
        searchInputRef={searchInputRef}
      />
    </div>
  );
}

export default App;
