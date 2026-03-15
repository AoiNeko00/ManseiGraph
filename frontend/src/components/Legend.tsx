import { COMMUNITY_COLORS, TYPE_LABELS, TYPE_ICONS } from '../constants';
import graphRawData from '../data.json';

// 범례 패널 Props
interface LegendProps {
  activeCommunities: Set<string>;
  activeTypes: Set<string>;
  handleCommunityToggle: (id: string) => void;
  handleTypeToggle: (type: string) => void;
}

// 통합 범례(unified legend) 패널 컴포넌트
export function Legend({
  activeCommunities,
  activeTypes,
  handleCommunityToggle,
  handleTypeToggle,
}: LegendProps) {
  return (
    <div className="legend">
      <div className="legend-section">
        <span className="legend-section-title">커뮤니티</span>
        <div className="legend-items">
          {Object.entries(COMMUNITY_COLORS).map(([id, color]) => {
            const sample = graphRawData.nodes.find((n) => (n as any).communityId === id);
            const label = (sample as any)?.communityName || id;
            const isActive = activeCommunities.has(id);
            return (
              <div
                key={id}
                className={`legend-item legend-item-interactive ${isActive ? '' : 'legend-item-dimmed'}`}
                onClick={() => handleCommunityToggle(id)}
                title={`${label} ${isActive ? '숨기기' : '표시'}`}
              >
                <span className="legend-dot" style={{ backgroundColor: color }} />
                <span>{label}</span>
              </div>
            );
          })}
        </div>
      </div>
      <div className="legend-divider" />
      <div className="legend-section">
        <span className="legend-section-title">유형</span>
        <div className="legend-items">
          {Object.entries(TYPE_LABELS).map(([type, label]) => {
            const IconComponent = TYPE_ICONS[type];
            const isActive = activeTypes.has(type);
            return (
              <div
                key={type}
                className={`legend-item legend-item-interactive ${isActive ? '' : 'legend-item-dimmed'}`}
                onClick={() => handleTypeToggle(type)}
                title={`${label} ${isActive ? '숨기기' : '표시'}`}
              >
                <IconComponent size={12} />
                <span>{label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
