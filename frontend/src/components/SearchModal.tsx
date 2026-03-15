import { Search, Circle } from 'lucide-react';
import type { GraphNode } from '../types';
import { TYPE_LABELS, TYPE_ICONS, COMMUNITY_COLORS, FALLBACK_COLOR } from '../constants';

// 검색 모달 Props
interface SearchModalProps {
  isSearchOpen: boolean;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  searchResults: GraphNode[];
  searchSelectedIndex: number;
  setSearchSelectedIndex: (index: number) => void;
  handleNodeClick: (node: any) => void;
  setIsSearchOpen: (open: boolean) => void;
  searchInputRef: React.RefObject<HTMLInputElement | null>;
}

// Quick Search 모달(search modal) 컴포넌트 — Cmd+K
export function SearchModal({
  isSearchOpen,
  searchQuery,
  setSearchQuery,
  searchResults,
  searchSelectedIndex,
  setSearchSelectedIndex,
  handleNodeClick,
  setIsSearchOpen,
  searchInputRef,
}: SearchModalProps) {
  if (!isSearchOpen) return null;

  return (
    <div className="search-overlay" onClick={() => setIsSearchOpen(false)}>
      <div className="search-modal" onClick={(e) => e.stopPropagation()}>
        <div className="search-input-wrapper">
          <Search size={18} className="search-icon" />
          <input
            ref={searchInputRef}
            type="text"
            className="search-input"
            placeholder="노드 이름 또는 설명 검색..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setSearchSelectedIndex(0);
            }}
          />
          <kbd className="search-kbd">ESC</kbd>
        </div>
        {searchResults.length > 0 && (
          <ul className="search-results">
            {searchResults.map((node, i) => {
              const IconComponent = TYPE_ICONS[node.type] || Circle;
              return (
                <li
                  key={node.id}
                  className={`search-result-item ${i === searchSelectedIndex ? 'search-result-selected' : ''}`}
                  onClick={() => {
                    handleNodeClick(node);
                    setIsSearchOpen(false);
                  }}
                  onMouseEnter={() => setSearchSelectedIndex(i)}
                >
                  <IconComponent size={14} className="search-result-type-icon" />
                  <span className="search-result-name">{node.name}</span>
                  <span className="search-result-type">{TYPE_LABELS[node.type]}</span>
                  <span
                    className="search-result-community-dot"
                    style={{ backgroundColor: COMMUNITY_COLORS[(node as any).communityId] || FALLBACK_COLOR }}
                  />
                </li>
              );
            })}
          </ul>
        )}
        {searchQuery.trim() && searchResults.length === 0 && (
          <div className="search-empty">검색 결과가 없습니다</div>
        )}
      </div>
    </div>
  );
}
