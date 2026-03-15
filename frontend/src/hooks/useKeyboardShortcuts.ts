import { useEffect } from 'react';
import type { GraphNode, GraphLink } from '../types';
import { SEED_NODE_ID } from '../constants';

interface UseKeyboardShortcutsDeps {
  isSearchOpen: boolean;
  searchResults: GraphNode[];
  searchSelectedIndex: number;
  selectedLink: GraphLink | null;
  selectedNode: GraphNode | null;
  setIsSearchOpen: (v: boolean) => void;
  setSearchQuery: (v: string) => void;
  setSearchSelectedIndex: React.Dispatch<React.SetStateAction<number>>;
  setSelectedLink: (v: GraphLink | null) => void;
  setSelectedNode: (v: GraphNode | null) => void;
  setExpandedNodes: React.Dispatch<React.SetStateAction<Set<string>>>;
  handleNodeClick: (node: any) => void;
  handleFitView: () => void;
  handleReset: () => void;
  handleZoomIn: () => void;
  handleZoomOut: () => void;
}

export function useKeyboardShortcuts(deps: UseKeyboardShortcutsDeps) {
  const {
    isSearchOpen,
    searchResults,
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
  } = deps;

  // 키보드 단축키(keyboard shortcuts)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInput = target.matches('input, textarea, [contenteditable]');

      // Cmd+K 또는 / 로 검색 모달 열기
      if ((e.metaKey && e.key === 'k') || (e.key === '/' && !isSearchOpen && !isInput)) {
        e.preventDefault();
        setIsSearchOpen(true);
        setSearchQuery('');
        setSearchSelectedIndex(0);
        return;
      }

      // ESC: 모든 패널 닫기(close all panels)
      if (e.key === 'Escape') {
        if (isSearchOpen) setIsSearchOpen(false);
        if (selectedLink) setSelectedLink(null);
        if (selectedNode) setSelectedNode(null);
        return;
      }

      // 검색 모달 내 ArrowUp/Down/Enter
      if (isSearchOpen) {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          setSearchSelectedIndex((i) => Math.min(i + 1, searchResults.length - 1));
        }
        if (e.key === 'ArrowUp') {
          e.preventDefault();
          setSearchSelectedIndex((i) => Math.max(i - 1, 0));
        }
        if (e.key === 'Enter' && searchResults.length > 0) {
          e.preventDefault();
          const node = searchResults[searchSelectedIndex];
          if (node) {
            handleNodeClick(node);
            setIsSearchOpen(false);
          }
        }
        return; // 검색 모달이 열려있으면 아래 단축키 무시
      }

      // input 요소에 포커스 중이면 단축키 무시
      if (isInput) return;

      // 0: 전체보기(zoomToFit)
      if (e.key === '0') {
        e.preventDefault();
        handleFitView();
        return;
      }

      // R: 초기화(reset)
      if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        handleReset();
        return;
      }

      // +/=: 줌 인
      if (e.key === '+' || e.key === '=') {
        e.preventDefault();
        handleZoomIn();
        return;
      }

      // -: 줌 아웃
      if (e.key === '-') {
        e.preventDefault();
        handleZoomOut();
        return;
      }

      // Backspace: 마지막 확장 노드 축소(undo)
      if (e.key === 'Backspace') {
        e.preventDefault();
        setExpandedNodes((prev) => {
          if (prev.size <= 1) return prev; // 시드 노드만 남으면 무시
          const arr = Array.from(prev);
          const last = arr[arr.length - 1];
          if (last === SEED_NODE_ID) return prev;
          const next = new Set(prev);
          next.delete(last);
          return next;
        });
        return;
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isSearchOpen, searchResults, searchSelectedIndex, selectedLink, selectedNode, handleNodeClick, handleFitView, handleReset, handleZoomIn, handleZoomOut, setIsSearchOpen, setSearchQuery, setSearchSelectedIndex, setSelectedLink, setSelectedNode, setExpandedNodes]);
}
