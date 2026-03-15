import { X } from 'lucide-react';
import type { GraphLink } from '../types';
import { getRelationLabel } from '../constants';

// 컨텍스트 패널 Props
interface ContextPanelProps {
  selectedLink: GraphLink | null;
  setSelectedLink: (link: GraphLink | null) => void;
  onClose?: () => void;
}

// 엣지 클릭 시 연결 근거(description + sourceContext) 표시 패널
export function ContextPanel({ selectedLink, setSelectedLink, onClose }: ContextPanelProps) {
  if (!selectedLink || (!(selectedLink as any).sourceContext && !(selectedLink as any).description)) {
    return null;
  }

  return (
    <div className="context-panel">
      <div className="context-header">
        <span className="context-label">연결 근거 (Why this connection?)</span>
        <button className="context-close" onClick={() => { setSelectedLink(null); onClose?.(); }}>
          <X size={16} />
        </button>
      </div>
      {(selectedLink as any).description && (
        <div className="context-description">
          <span className="context-sub-label">AI 추출 근거</span>
          <p className="context-text">{(selectedLink as any).description}</p>
        </div>
      )}
      {(selectedLink as any).sourceContext && (
        <div className="context-source">
          <span className="context-sub-label">원본 발췌문</span>
          <p className="context-text">{(selectedLink as any).sourceContext}</p>
        </div>
      )}
      <div className="context-meta">
        <span className="context-relation">
          {getRelationLabel((selectedLink as any).relation)}
        </span>
        {(selectedLink as any).strength && (
          <span className="context-relation" style={{ marginLeft: 8, opacity: 0.7 }}>
            강도 {(selectedLink as any).strength}/10
          </span>
        )}
      </div>
    </div>
  );
}
