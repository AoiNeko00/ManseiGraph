import { Circle, Hexagon, Diamond, Square, Triangle } from 'lucide-react';
import graphRawData from './data.json';

// 노드 타입별 한국어 라벨
export const TYPE_LABELS: Record<string, string> = {
  person: '인물',
  organization: '단체',
  event: '사건',
  location: '지역',
  concept: '개념',
};

// 관계(relation) 한국어 매핑 — data.json의 전체 relation 타입 커버
export const RELATION_LABELS: Record<string, string> = {
  // ── 행위(action) ──
  participated_in: '참여', participated: '참여', participated_in_suppression: '탄압참여',
  participated_then_opposed: '참여후대항',
  founded: '창립', co_founded: '공동창립', 'co-founded': '공동창립', founded_by: '창립됨',
  established: '설립', established_by: '설립됨', established_basis: '기반마련',
  established_base: '거점설립', established_in: '설립지',
  supported_founding: '설립지원',
  led: '주도', led_by: '주도됨', led_branch: '분회주도', led_to: '초래',
  organized: '조직', planned: '기획', prepared: '준비',
  authored: '저술', authored_for: '기고', wrote_for: '기고',
  wrote_biography_of: '전기저술', published: '출판', documents: '기록',
  signed: '서명', created: '생성', initiated: '개시',
  performed: '수행', committed: '실행', conducted_funeral: '장례집행',
  administered_sacraments: '성사집전',
  // ── 구조(structure) ──
  member_of: '소속', was_member_of: '소속', affiliated_with: '소속',
  belongs_to: '소속', core_member: '핵심구성원',
  member_of_organization_led_by: '소속(지도자)',
  served_in: '복무', served_under: '휘하복무', worked_at: '근무', worked_for: '근무',
  worked_under: '하위근무', was_officer_of: '장교역임',
  allied_with: '연합', collaborated_with: '협력', negotiated_with: '교섭',
  joined: '합류', enrolled_in: '입학', trained_at: '훈련',
  part_of: '소속', was_part_of: '소속', includes: '포함',
  organ_of: '기관', subsidiary_of: '산하',
  subordinate_of: '예속', became_subordinate_of: '예속됨',
  organizational_base: '조직거점',
  // ── 영향(influence) ──
  influenced: '영향', influenced_by: '영향받음',
  inspired: '영감', inspired_by: '영감받음',
  mentor_of: '사제관계', student_of: '사사',
  supported: '지원', supported_by: '지원받음',
  contributed_to: '기여', indirectly_contributed_to: '간접기여',
  motivated: '동기부여', facilitated: '촉진', mediated_by: '중재됨',
  aided_by: '원조받음', assisted: '보조', helped: '도움',
  recommended: '추천', recommended_by: '추천받음',
  advised: '자문', informed: '정보제공',
  attracted: '유인', recruited: '모집',
  ideological_basis_of: '이념기반', legal_basis_for: '법적근거',
  shared_cause: '대의공유',
  // ── 대립(conflict) ──
  opposed: '대항', rivaled: '경쟁', conflicted_with: '갈등',
  attacked: '공격', suppressed: '탄압',
  killed: '처형', killed_by: '피살',
  assassinated: '암살', assassinated_by: '피암살',
  assassination_attempted: '암살시도', attempted_assassination_of: '암살시도', attempted_assassination: '암살시도',
  arrested: '체포', arrested_by: '체포됨', was_arrested_in: '수감',
  victim_of: '피해', was_victim_of: '피해',
  sentenced_by: '선고받음', imprisoned_in: '수감',
  interrogated: '심문', punished: '처벌',
  executed: '처형됨', executed_at: '처형장소',
  perpetrated: '자행', perpetrated_by: '자행됨',
  coerced: '강압', forced_by: '강제됨',
  forced_signing: '강제서명', forced_abdication_of: '강제퇴위', caused_abdication_of: '퇴위야기',
  invaded_by: '침략받음', destroyed: '파괴',
  targeted: '대상', targeted_at: '표적',
  tried_to_stop: '저지시도', fought_against: '교전', fought_in: '참전',
  excluded_from: '배제', expelled: '추방', defected_from: '이탈',
  criticized_ideology: '이념비판', criticized_by: '비판받음',
  avoided: '회피', declined: '거부', resigned_from: '사임',
  disillusioned_by: '환멸',
  // ── 가족(family) ──
  family: '가족', family_of: '가족', family_relation: '가족', family_connected: '가족연결',
  family_kinship: '혈연', kinship_of: '친족',
  parent_of: '부모', child_of: '자녀', sibling_of: '형제자매', sibling: '형제자매',
  grandchild_of: '손자녀', son_of: '아들', son_in_law_of: '사위', descendant_of: '후손',
  married_to: '배우자', spouse: '배우자', spouse_of: '배우자',
  // ── 공간(spatial) ──
  located_in: '위치', location_of: '소재지',
  based_in: '거점', base_of: '거점', active_in: '활동지', activity_location: '활동장소',
  operated_in: '활동지역', operated: '운영',
  resided_in: '거주', born_in: '출생지', birthplace_of: '출생지',
  died_in: '사망지', scene_of: '현장', site_of: '현장',
  execution_site_of: '처형지', destination_of: '목적지',
  fled_from: '도주', emigrated_to: '망명', relocated_to: '이전',
  passed_through: '경유', dispatched_to: '파견', deployed: '배치',
  sent_members_to: '파원',
  활동_거점: '활동거점', 관련_지역: '관련지역', 망명지: '망명지',
  geographically_related: '지리적관련',
  // ── 조직 변천(evolution) ──
  evolved_into: '발전', merged_with: '통합', merged_into: '통합됨',
  split_from: '분리', succeeded_by: '후임', succeeded: '계승',
  preceded: '전임', preceded_by: '전임', preceded_context: '선행맥락',
  transferred_leadership_to: '지도부이양', dissolved: '해산',
  // ── 교육(education) ──
  studied_at: '수학', educated_at: '수학', graduated_from: '졸업',
  taught_at: '교직', taught: '교육', studied_together: '동문',
  // ── 의사소통(communication) ──
  communicated_with: '교류', contacted_through: '접촉',
  received_information_from: '정보수신', reported_to: '보고', reported_on: '보도',
  petitioned: '청원', requested_from: '요청',
  testified_about: '증언', witnessed: '목격', was_recorded_by: '기록됨',
  // ── 기타(general) ──
  related_to: '관련', related: '관련', associated_with: '관련', connected_to: '연결',
  involved_in: '관여', implicated_in: '연루',
  triggered: '촉발', caused: '야기', caused_by: '기인',
  affected: '영향받음', affected_by: '영향받음', indirectly_affected: '간접영향',
  followed: '후속', responded_to: '대응', changed: '변화',
  same_as: '동일', name_shared_with: '동명',
  compared_to: '비교', symbolically_compared: '상징비교',
  contemporary_of: '동시대', met: '만남', met_with: '회동',
  knew_personally: '친분', acquaintance_with: '면식',
  recognized: '인정', recognized_by: '인정받음',
  respected_by: '존경받음', respected_and_preserved: '존경·보전',
  memorialized: '추모', recovered_remains: '유해수습',
  buried_with: '합장', passed_remains_to: '유해인도',
  documented_by: '기록됨', documented: '기록', exposed: '폭로', origin_of: '기원',
  managed: '관리', directed: '지휘', directed_by: '지휘됨',
  commanded: '지휘', commissioned: '위임',
  controlled_by: '통제됨', attended: '참석', attended_by: '참석됨',
  employed: '고용', protected: '보호', defended: '방어',
  attempted_alliance: '연합시도',
};

// RELATION_LABELS에 없는 관계는 밑줄(underscore)을 공백으로 치환
export function getRelationLabel(relation: string): string {
  return RELATION_LABELS[relation] ?? relation.replace(/_/g, ' ');
}

// 커뮤니티(community)별 파스텔 색상 팔레트
// 커뮤니티 색상 팔레트(palette) — 12색 파스텔 + uncategorized
const PALETTE = [
  '#7EB8DA',  // 하늘빛 파스텔
  '#E8A87C',  // 살구빛 파스텔
  '#D4A5C9',  // 연보라 파스텔
  '#95C8A0',  // 연초록 파스텔
  '#F0C27B',  // 밀색 파스텔
  '#E8B4B8',  // 분홍 파스텔
  '#A8C8E8',  // 연청 파스텔
  '#C9B8E8',  // 라벤더 파스텔
  '#F0D4A0',  // 크림 파스텔
  '#A8D8C8',  // 민트 파스텔
  '#D8C0A0',  // 모카 파스텔
  '#B8D8E8',  // 아이스블루 파스텔
];

// data.json의 커뮤니티 목록에서 동적으로 색상 할당
function buildCommunityColors(): Record<string, string> {
  const colors: Record<string, string> = {};
  const communities = (graphRawData as any).communities || [];
  communities.forEach((c: { id: string }, i: number) => {
    if (c.id === 'uncategorized') {
      colors[c.id] = '#B0B0B0';
    } else {
      colors[c.id] = PALETTE[i % PALETTE.length];
    }
  });
  colors['uncategorized'] = '#B0B0B0';
  return colors;
}

function buildHullColors(communityColors: Record<string, string>): Record<string, string> {
  const hullColors: Record<string, string> = {};
  for (const [id, hex] of Object.entries(communityColors)) {
    // hex → rgba(r,g,b,0.10)
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const alpha = id === 'uncategorized' ? 0.05 : 0.10;
    hullColors[id] = `rgba(${r},${g},${b},${alpha})`;
  }
  return hullColors;
}

export const COMMUNITY_COLORS: Record<string, string> = buildCommunityColors();
export const COMMUNITY_HULL_COLORS: Record<string, string> = buildHullColors(COMMUNITY_COLORS);

export const FALLBACK_COLOR = '#B0B0B0';

// 관계(relation)별 엣지 색상
export const RELATION_COLORS: Record<string, string> = {
  participated_in: '#2d3748',  // 참여 — 진한 남색
  member_of:       '#2c5e3f',  // 소속 — 진한 녹색
  founded:         '#7c4a1e',  // 창립 — 진한 갈색
  led:             '#8b2f2f',  // 주도 — 진한 적색
  allied_with:     '#4a3d80',  // 연합 — 진한 보라
  influenced:      '#8b6914',  // 영향 — 진한 금색
  opposed:         '#a83232',  // 대항 — 선명한 적색
  located_in:      '#4a5568',  // 위치 — 진한 회색
  related_to:      '#5a6070',  // 관련 — 중간 회색
};

// 관계(relation) 카테고리별 대시(dash) 패턴
export const RELATION_DASH: Record<string, number[]> = {
  participated_in: [],         // 행위(action) — 실선
  founded:         [],
  led:             [],
  member_of:       [8, 4],     // 구조(structure) — 긴 점선
  allied_with:     [8, 4],
  influenced:      [4, 4],     // 영향(influence) — 짧은 점선
  opposed:         [4, 4],
  located_in:      [2, 4],     // 공간/일반(spatial) — 점
  related_to:      [2, 4],
};

// 타입별 아이콘 매핑(type icon mapping)
export const TYPE_ICONS: Record<string, typeof Circle> = {
  person: Circle,
  organization: Hexagon,
  event: Diamond,
  location: Square,
  concept: Triangle,
};

// 시작 노드(seed node)
const SEED_NODE_ID_CANDIDATE = 'org_provisional_govt';
export const SEED_NODE_ID = graphRawData.nodes.some((n) => n.id === SEED_NODE_ID_CANDIDATE)
  ? SEED_NODE_ID_CANDIDATE
  : graphRawData.nodes[0]?.id ?? '';
