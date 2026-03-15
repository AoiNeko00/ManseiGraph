// 타입 정의(type definitions)

export interface GraphNode {
  id: string;
  name: string;
  type: 'person' | 'organization' | 'event' | 'location' | 'concept';
  description: string;
  degree: number;
  reasoning?: string;
  insight?: string;
  communityId?: string;
  communityName?: string;
  communitySummary?: string;
  x?: number;
  y?: number;
}

export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  weight: number;
  strength?: number;
  relation: string;
  description?: string;
  sourceContext?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}
