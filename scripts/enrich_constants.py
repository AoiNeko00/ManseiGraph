"""enrich_graph.py에서 사용하는 상수 정의.

커뮤니티(community) 정의와 타입 분류 추론 근거(reasoning) 템플릿을 포함한다.
"""

# ─── 타입 분류 추론 근거(reasoning) 템플릿 ───

TYPE_REASONING = {
    "person": "이 노드는 특정 개인의 이름과 행적(활동, 직책, 역할)을 서술하고 있어 '인물(person)' 타입으로 분류되었다.",
    "organization": "이 노드는 조직·단체·기관의 명칭과 그 활동 목적·구성을 서술하고 있어 '단체(organization)' 타입으로 분류되었다.",
    "event": "이 노드는 특정 시점에 발생한 역사적 사건·운동의 명칭과 경위를 서술하고 있어 '사건(event)' 타입으로 분류되었다.",
    "location": "이 노드는 지리적 장소·행정구역의 명칭과 위치 정보를 서술하고 있어 '장소(location)' 타입으로 분류되었다.",
    "concept": "이 노드는 추상적 이념·원칙·전략의 명칭과 의미를 서술하고 있어 '개념(concept)' 타입으로 분류되었다.",
}

# ─── 커뮤니티(community) 정의 ───

COMMUNITIES = {
    "shanghai_diplomacy": {
        "name": "상하이 외교라인",
        "summary": "대한민국 임시정부를 중심으로 상하이에서 활동한 외교·정치 노선의 독립운동 네트워크. 파리 강화회의 대표 파견, 구미위원부 운영 등 국제 외교를 통한 독립 쟁취를 추구했다.",
        "keywords": ["임시정부", "파리", "외교", "구미위원부", "파리위원부", "상하이",
                      "신한청년당", "동제사", "위원부"],
        "node_ids": ["org_provisional_govt", "org_paris_commission", "org_europe_commission",
                     "org_sinhan_youth", "org_dongjesa", "org_independence_news",
                     "org_daehan_gukmin", "org_hanseong_govt",
                     "person_kim_kyusik", "person_yeo_unhyeong", "person_seo_jaepil",
                     "person_lee_seungman", "person_shin_kyusik", "person_seo_byeongho",
                     "person_lee_dongnyeong", "person_lee_gwanyong", "person_jang_taeksang",
                     "person_kim_gu", "person_jo_soan", "person_shin_chaeho",
                     "person_hong_myeonghee", "person_jeon_deokgi",
                     "person_wilson", "person_sunwen", "person_lee_gwangsoo",
                     "person_kim_sunae", "person_jo_byeongok",
                     "org_patriotic_women",
                     "event_paris_conference", "event_march_first", "event_left_right_coalition",
                     "event_north_south_talks", "event_korean_war",
                     "event_wumu_declaration", "event_feb28_declaration", "event_wwi",
                     "location_paris", "location_shanghai", "location_washington",
                     "location_hongcheon", "location_ulaanbaatar",
                     "concept_self_determination", "concept_left_right_unity", "concept_trusteeship",
                     "org_roanoke", "org_princeton", "org_joseon_minjok_revolution",
                     "org_minjok_jaju", "org_namjoseon_assembly",
                     "event_105_incident"]
    },
    "armed_struggle_manchuria": {
        "name": "만주 무장투쟁",
        "summary": "만주·간도 지역을 무대로 전개된 무장 독립투쟁 네트워크. 봉오동·청산리 전투 등 군사적 성과를 거두었으나, 간도 참변 등 일제의 보복 학살에도 직면했다.",
        "keywords": ["간도", "만주", "전투", "봉오동", "청산리", "참변", "학살", "독립군"],
        "node_ids": ["e_gando_massacre", "e_hunchun", "e_cheongsan", "e_bongodong",
                     "e_jangam", "e_baekun", "e_songeon",
                     "o_imperial_army", "o_bukgando", "o_19div", "o_14div",
                     "o_bukgando_council", "o_donga", "o_gando_detachment",
                     "p_jang_deokjun", "p_martin", "p_foote",
                     "p_lee_yongjeom", "p_jang_duhwan",
                     "l_gando", "l_yanbian", "l_jilin", "l_manchuria",
                     "l_jangam_village", "l_hwaryong", "l_yongjeong",
                     "l_baekun_village", "l_myeongdong_school", "l_yeongilhyeon",
                     "c_independence_movement", "c_scorched_earth", "c_suppression_plan"]
    },
    "uiyeol_resistance": {
        "name": "의열투쟁 노선",
        "summary": "폭탄 투척·암살 등 직접 행동을 통해 일제 요인과 식민 기관을 타격한 의열투쟁 네트워크. 강우규의 사이토 총독 저격 의거 등이 대표적이다.",
        "keywords": ["의거", "폭탄", "저격", "암살", "의열"],
        "node_ids": ["kang_u_gyu", "saito_makoto", "hasegawa_yoshimichi",
                     "heo_hyeong", "oh_tae_yeong", "jang_ik_gyu", "im_seung_hwa",
                     "kim_tae_seok", "oliver_avison", "yun_chi_ho",
                     "gye_bong_u", "lee_seung_gyo", "kim_chi_bo", "park_eun_sik",
                     "kang_jung_geun", "kang_young_jae",
                     "noindan", "joseon_chongdokbu", "gwangdong_school",
                     "seodaemun_prison", "namdaemun_station",
                     "deokcheon", "hongwon", "bukgando", "raohe_county",
                     "vladivostok", "sinheung_village", "gyeongseong", "jilin_province",
                     "march_1_movement", "eulsa_treaty", "joseon_annexation",
                     "saito_bombing",
                     "independence_movement", "uiyeol_struggle", "national_consciousness"]
    },
    "june_10_movement": {
        "name": "6·10 만세운동 네트워크",
        "summary": "1926년 순종 장례일을 계기로 학생·사회주의·천도교 세력이 연합하여 일으킨 항일 만세운동의 참여자·단체 네트워크. 이후 신간회·근우회 결성에 영향을 미쳤다.",
        "keywords": ["6·10", "순종", "만세", "조선공산당"],
        "node_ids": ["event_610", "event_31", "event_gwangju", "event_sunjong_funeral",
                     "person_gangdalyeong", "person_gwonoseol", "person_kimdanya",
                     "person_leejitrak", "person_minyeongsik", "person_leeminjae",
                     "person_leebyeongip", "person_bakhakyun", "person_leehyeonsang",
                     "person_leechonjin", "person_baknaeown", "person_gwondongjin",
                     "person_sunjong", "person_songjinu", "person_jeonginho",
                     "person_bakheonnyeong", "person_hirohito",
                     "org_joseoncommparty", "org_koreayouth", "org_singanhoe",
                     "org_geunuhoe", "org_sinjonghoe", "org_yeonjeonghoe",
                     "org_cheondogyo", "org_yonhee", "org_junganggobo", "org_kyeongseong",
                     "org_japanempire",
                     "location_gyeongseongbu", "location_jongno", "location_joseon",
                     "location_seodaemun",
                     "concept_antijapan", "concept_socialism"]
    },
    "national_sovereignty_loss": {
        "name": "국권 피탈 과정",
        "summary": "을사늑약(1905)부터 경술국치(1910)에 이르는 대한제국의 국권 상실 과정과 관련된 노드 군집. 일본 제국의 침략과 친일파의 협력, 그리고 이에 대한 저항이 핵심이다.",
        "keywords": ["병합", "을사", "경술", "조약", "국권"],
        "node_ids": ["event_annexation", "event_treaty",
                     "org_japan_empire", "org_daehan_empire", "org_joseon",
                     "group_chinilpa", "person_emperor_japan",
                     "concept_gwonpital",
                     "event_russo_japanese_war"]
    },
    "women_social_movement": {
        "name": "여성·사회운동",
        "summary": "근우회를 중심으로 전개된 여성 해방 운동과 좌우합작 사회운동 네트워크. 기독교·불교·사회주의 등 다양한 이념적 배경의 여성 지도자들이 참여했다.",
        "keywords": ["근우회", "여성", "사회운동"],
        "node_ids": ["geunuhoe", "singanhoe",
                     "kim_hwallan", "go_hwanggyeong", "park_chajeong",
                     "jeong_chilseong", "park_suncheon",
                     "yu_gakgyeong", "cha_mirisa", "hwang_sindeok",
                     "choi_eunhee", "kim_iryeop", "kim_gwangho", "yu_yeongjun",
                     "joseon_ywca", "joseon_buddhist_women", "japanese_empire",
                     "socialism", "christianity", "women_movement",
                     "chungcheongnam", "creation_event", "dissolution_event"]
    },
    "education_enlightenment": {
        "name": "교육·계몽 운동",
        "summary": "교육 기관 설립과 언론·출판을 통한 민족의식 고양 활동 네트워크. 경신학교, 황성기독교청년회 등 기독교 계열 교육기관이 중심이었다.",
        "keywords": ["학교", "교육", "계몽", "YMCA"],
        "node_ids": ["org_gyeongsin", "org_ymca",
                     "person_underwood", "person_uichinwang",
                     "person_ham_taeyeong", "person_jo_mansik",
                     "person_yun_chiho"]
    }
}
