import { useState, useRef } from 'react';
import { MessageCircle, Send, X, Globe, MapPin, Loader2, Compass } from 'lucide-react';
import graphRawData from '../data.json';

// 검색 응답(search response) 타입
interface SearchResult {
  answer: string;
  activated_nodes: string[];
  activated_communities: string[];
  search_type: string;
}

interface QueryPanelProps {
  onSearchResult: (result: SearchResult) => void;
  onClearHighlight: () => void;
  onNodeNavigate?: (nodeId: string) => void;
}

const API_BASE = 'http://localhost:8000';

// GraphRAG 자연어 질의(query) 패널
export function QueryPanel({ onSearchResult, onClearHighlight, onNodeNavigate }: QueryPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState<'local' | 'global' | 'drift'>('local');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = async () => {
    if (!query.trim() || isLoading) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim(), search_type: searchType }),
      });

      if (!response.ok) {
        throw new Error(`서버 오류: ${response.status}`);
      }

      const data: SearchResult = await response.json();
      setResult(data);
      onSearchResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '알 수 없는 오류');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleClose = () => {
    setIsOpen(false);
    setResult(null);
    setError(null);
    onClearHighlight();
  };

  // 답변 텍스트에서 활성화 노드명을 클릭 가능한 링크로 변환
  const formatAnswerWithLinks = (answer: string, activatedNodeIds: string[]): string => {
    let html = formatMarkdown(answer);

    // 활성화된 노드의 이름 수집 (긴 이름부터 매칭하여 부분 대체 방지)
    const namesToLink: { name: string; nodeId: string }[] = [];
    for (const nodeId of activatedNodeIds) {
      const node = graphRawData.nodes.find(n => n.id === nodeId);
      if (node) {
        const baseName = node.name.split('(')[0].trim();
        if (baseName.length >= 2) {
          namesToLink.push({ name: baseName, nodeId });
        }
      }
    }
    // 긴 이름부터 처리 (부분 대체 방지)
    namesToLink.sort((a, b) => b.name.length - a.name.length);

    // 이미 태그 안에 있는 텍스트는 건너뛰도록 마커 사용
    for (const { name, nodeId } of namesToLink) {
      const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`(?<!<[^>]*)(?<!data-node-id="[^"]*)(${escaped})(?![^<]*>)`, 'g');
      html = html.replace(regex,
        `<span class="query-node-link" data-node-id="${nodeId}">$1</span>`
      );
    }

    return html;
  };

  // 답변 영역 클릭 핸들러 (이벤트 위임)
  const handleResultClick = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.classList.contains('query-node-link') && onNodeNavigate) {
      const nodeId = target.getAttribute('data-node-id');
      if (nodeId) onNodeNavigate(nodeId);
    }
  };

  if (!isOpen) {
    return (
      <button
        className="query-toggle-btn"
        onClick={() => setIsOpen(true)}
        title="GraphRAG 질의"
      >
        <MessageCircle size={20} />
      </button>
    );
  }

  return (
    <div className="query-panel">
      <div className="query-panel-header">
        <h3 className="query-panel-title">
          <MessageCircle size={16} />
          GraphRAG 질의
        </h3>
        <button className="query-close-btn" onClick={handleClose}>
          <X size={16} />
        </button>
      </div>

      {/* 검색 타입(search type) 선택 */}
      <div className="query-type-selector">
        <button
          className={`query-type-btn ${searchType === 'local' ? 'active' : ''}`}
          onClick={() => setSearchType('local')}
          title="관련 엔티티 중심 검색"
        >
          <MapPin size={14} />
          Local Search
        </button>
        <button
          className={`query-type-btn ${searchType === 'drift' ? 'active' : ''}`}
          onClick={() => setSearchType('drift')}
          title="로컬에서 시작하여 점진적 확장"
        >
          <Compass size={14} />
          DRIFT
        </button>
        <button
          className={`query-type-btn ${searchType === 'global' ? 'active' : ''}`}
          onClick={() => setSearchType('global')}
          title="커뮤니티 리포트 기반 전역 검색"
        >
          <Globe size={14} />
          Global
        </button>
      </div>

      {/* 질의 입력(query input) */}
      <div className="query-input-wrapper">
        <textarea
          ref={inputRef}
          className="query-input"
          placeholder="독립운동에 대해 질문하세요..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={3}
        />
        <button
          className="query-submit-btn"
          onClick={handleSubmit}
          disabled={isLoading || !query.trim()}
        >
          {isLoading ? <Loader2 size={16} className="spinning" /> : <Send size={16} />}
        </button>
      </div>
      <div className="query-hint">⌘+Enter로 전송</div>

      {/* 오류 표시(error display) */}
      {error && (
        <div className="query-error">
          {error}
        </div>
      )}

      {/* 결과 표시(result display) */}
      {result && (
        <div className="query-result">
          <div className="query-result-header">
            <span className="query-result-type-badge">
              {result.search_type === 'global' ? (
                <><Globe size={12} /> Global</>
              ) : result.search_type === 'drift' ? (
                <><Compass size={12} /> DRIFT</>
              ) : (
                <><MapPin size={12} /> Local</>
              )}
            </span>
            {result.activated_nodes.length > 0 && (
              <span className="query-result-stats">
                {result.activated_nodes.length}개 노드 활성화
              </span>
            )}
          </div>
          <div
            className="query-result-content"
            onClick={handleResultClick}
            dangerouslySetInnerHTML={{
              __html: formatAnswerWithLinks(result.answer, result.activated_nodes),
            }}
          />
        </div>
      )}
    </div>
  );
}

// 간단한 마크다운(markdown) → HTML 변환
function formatMarkdown(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/\n/g, '<br/>');
}
