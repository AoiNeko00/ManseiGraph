import { useMemo, useState, useEffect } from 'react';
import { BookOpen, Lightbulb, Users, FileCheck, ChevronRight, X } from 'lucide-react';
import type { GraphNode } from '../types';
import { TYPE_LABELS, COMMUNITY_COLORS, FALLBACK_COLOR } from '../constants';
import graphRawData from '../data.json';

// 사이드 패널 Props
interface SidePanelProps {
  selectedNode: GraphNode | null;
  hoveredNode: GraphNode | null;
  hoveredConnectionId: string | null;
  activeTab: 'reasoning' | 'insight' | 'community' | 'claims';
  setActiveTab: (tab: 'reasoning' | 'insight' | 'community' | 'claims') => void;
  handleNodeClick: (node: any) => void;
  setSelectedNode: (node: GraphNode | null) => void;
  setHoveredConnectionId: (id: string | null) => void;
  getNodeColor: (node: any) => string;
  selectedConnections: { id: string; name: string; type: string; relation: string }[];
}

// 사이드 패널(side panel) 컴포넌트 — GraphRAG 상세 정보
export function SidePanel({
  selectedNode,
  hoveredNode,
  hoveredConnectionId,
  activeTab,
  setActiveTab,
  handleNodeClick,
  setSelectedNode,
  setHoveredConnectionId,
  getNodeColor,
  selectedConnections,
}: SidePanelProps) {
  return (
    <div className={`side-panel ${selectedNode ? 'open' : ''}`}>
      {selectedNode && (
        <>
          <div className="panel-header">
            <div
              className="panel-type-badge"
              style={{ backgroundColor: getNodeColor(selectedNode as any) }}
            >
              {TYPE_LABELS[selectedNode.type]}
            </div>
            <button
              className="panel-close"
              onClick={() => setSelectedNode(null)}
            >
              <X size={18} />
            </button>
          </div>

          <h2 className="panel-title">{selectedNode.name}</h2>
          <p className="panel-description">{selectedNode.description}</p>

          <div className="panel-stats">
            <div className="stat-item">
              <span className="stat-label">연결 수</span>
              <span className="stat-value">{selectedNode.degree}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">커뮤니티</span>
              <span className="stat-value community-name">
                <span
                  className="community-dot"
                  style={{ backgroundColor: getNodeColor(selectedNode as any) }}
                />
                {(selectedNode as any).communityName || '-'}
              </span>
            </div>
          </div>

          {/* GraphRAG 탭 네비게이션 */}
          <div className="panel-tabs">
            <button
              className={`panel-tab ${activeTab === 'reasoning' ? 'active' : ''}`}
              onClick={() => setActiveTab('reasoning')}
            >
              <BookOpen size={14} />
              추출 근거
            </button>
            <button
              className={`panel-tab ${activeTab === 'insight' ? 'active' : ''}`}
              onClick={() => setActiveTab('insight')}
            >
              <Lightbulb size={14} />
              역사적 통찰
            </button>
            <button
              className={`panel-tab ${activeTab === 'community' ? 'active' : ''}`}
              onClick={() => setActiveTab('community')}
            >
              <Users size={14} />
              커뮤니티
            </button>
            <button
              className={`panel-tab ${activeTab === 'claims' ? 'active' : ''}`}
              onClick={() => setActiveTab('claims')}
            >
              <FileCheck size={14} />
              역사적 사실
            </button>
          </div>

          {/* 탭 내용(tab content) */}
          <div className="panel-tab-content">
            {activeTab === 'reasoning' && (
              <div className="tab-section">
                <p className="tab-text">
                  {(selectedNode as any).reasoning || '추출 근거 정보가 없습니다.'}
                </p>
              </div>
            )}
            {activeTab === 'insight' && (
              <div className="tab-section">
                <p className="tab-text">
                  {(selectedNode as any).insight || '역사적 통찰 정보가 없습니다.'}
                </p>
              </div>
            )}
            {activeTab === 'community' && (
              <div className="tab-section">
                <p className="tab-text">
                  {(selectedNode as any).communitySummary || '커뮤니티 요약 정보가 없습니다.'}
                </p>
              </div>
            )}
            {activeTab === 'claims' && (
              <ClaimsTab nodeName={selectedNode.name} />
            )}
          </div>

          {/* 연결 목록 — 관계 타입별 그룹, 그룹 내 가나다순 */}
          {selectedConnections.length > 0 && (
            <ConnectionList
              connections={selectedConnections}
              hoveredNode={hoveredNode}
              hoveredConnectionId={hoveredConnectionId}
              handleNodeClick={handleNodeClick}
              setHoveredConnectionId={setHoveredConnectionId}
            />
          )}
        </>
      )}
    </div>
  );
}

// 관계 타입별 그룹화된 연결 목록(connection list)
function ConnectionList({
  connections,
  hoveredNode,
  hoveredConnectionId,
  handleNodeClick,
  setHoveredConnectionId,
}: {
  connections: SidePanelProps['selectedConnections'];
  hoveredNode: GraphNode | null;
  hoveredConnectionId: string | null;
  handleNodeClick: (node: any) => void;
  setHoveredConnectionId: (id: string | null) => void;
}) {
  // 관계(relation) 타입별 그룹핑 + 그룹 내 동일 노드 중복 제거 + 가나다순 정렬
  const grouped = useMemo(() => {
    const map = new Map<string, typeof connections>();
    for (const conn of connections) {
      const group = map.get(conn.relation) ?? [];
      // 같은 relation 그룹 내 동일 노드 중복 방지
      if (!group.some(c => c.id === conn.id)) {
        group.push(conn);
      }
      map.set(conn.relation, group);
    }
    // 그룹 내 가나다순
    for (const group of map.values()) {
      group.sort((a, b) => a.name.localeCompare(b.name, 'ko'));
    }
    // 그룹은 노드 수 내림차순
    return [...map.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [connections]);

  return (
    <div className="panel-connections">
      <h3>연결된 노드 ({new Set(connections.map(c => c.id)).size})</h3>
      {grouped.map(([relation, conns]) => (
        <div key={relation} className="conn-group">
          <div className="conn-group-title">
            <span>{relation}</span>
            <span className="conn-group-count">{conns.length}</span>
          </div>
          <ul>
            {conns.map((conn) => {
              const targetNode = graphRawData.nodes.find(n => n.id === conn.id);
              const isHighlighted = hoveredNode?.id === conn.id || hoveredConnectionId === conn.id;
              return (
                <li
                  key={conn.id}
                  className={isHighlighted ? 'conn-highlighted' : ''}
                  style={{ cursor: 'pointer' }}
                  onClick={() => {
                    if (targetNode) handleNodeClick(targetNode);
                  }}
                  onMouseEnter={() => setHoveredConnectionId(conn.id)}
                  onMouseLeave={() => setHoveredConnectionId(null)}
                >
                  <span
                    className="conn-dot"
                    style={{ backgroundColor: COMMUNITY_COLORS[(targetNode as any)?.communityId] || FALLBACK_COLOR }}
                  />
                  <span className="conn-name">{conn.name}</span>
                  <ChevronRight size={14} className="conn-arrow" />
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}

// Claims 탭 컴포넌트
interface Claim {
  subject: string;
  object: string;
  claim_type: string;
  status: string;
  start_date: string;
  end_date: string;
  description: string;
}

function ClaimsTab({ nodeName }: { nodeName: string }) {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setClaims([]);

    fetch(`http://localhost:8000/api/claims/${encodeURIComponent(nodeName)}`)
      .then(res => res.json())
      .then(data => {
        if (!cancelled) setClaims(data.claims || []);
      })
      .catch(() => {
        if (!cancelled) setClaims([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [nodeName]);

  if (loading) {
    return <div className="tab-section"><p className="tab-text">로딩 중...</p></div>;
  }

  if (claims.length === 0) {
    return (
      <div className="tab-section">
        <p className="tab-text">
          이 엔티티의 역사적 사실이 아직 추출되지 않았습니다.
          <br /><code>python3 scripts/extract_claims.py</code>를 실행하세요.
        </p>
      </div>
    );
  }

  return (
    <div className="tab-section">
      {claims.map((claim, i) => (
        <div key={i} className="claim-item">
          <div className="claim-header">
            <span className={`claim-status claim-status-${claim.status.toLowerCase()}`}>
              {claim.status}
            </span>
            <span className="claim-type">{claim.claim_type}</span>
          </div>
          <p className="claim-description">{claim.description}</p>
          {claim.object && claim.object !== 'NONE' && (
            <p className="claim-object">대상: {claim.object}</p>
          )}
          {claim.start_date && claim.start_date !== 'NONE' && (
            <p className="claim-date">
              {claim.start_date === claim.end_date
                ? claim.start_date.split('T')[0]
                : `${claim.start_date.split('T')[0]} ~ ${claim.end_date.split('T')[0]}`}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
