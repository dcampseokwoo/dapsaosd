"""G5 실제 500/HAX 포트폴리오 27개사 축별 레벨 — 격리 세션 분류(개선 §3·§4).

두 격리 세션이 classify_p_A/B.json(창업자 이력 founder_career 포함) + 개선 규칙만
보고 분류. hax 기업은 [후행] 사실 제외. 값 형식: 축 → (레벨|None, 근거, 대안|None).
"""
from __future__ import annotations

LEVELS_PORTFOLIO: dict[str, dict[str, tuple]] = {
    "peoplefund": {
        "traction": (4, "온투업계 최대 규모로 운영되는 대출중개(유상거래 모델) 실운영이 명시됨.", None),
        "team": (None, "창업자 김대윤/이수환 개인 경력이 '상세 확인 필요'로 특정되지 않음.", None),
        "market": (None, "덱·시장 논증 문서가 없어 상향 판정 불가.", None),
        "moat": (3, "규모·AI 사기탐지 자산은 존재하나 제3자 부여 우위 확인이 없음.", None),
    },
    "spoonradio": {
        "traction": (5, "매출 230억·전년비 900%+ 성장에 조달 67.5억 대비 높은 자본 효율.", None),
        "team": (3, "최혁재 전 LG전자 개발자로 관련 엔지니어링 도메인·초기 창업.", None),
        "market": (None, "덱·시장 논증 문서 없어 상향 판정 불가.", None),
        "moat": (3, "라이브 오디오 크리에이터 네트워크는 있으나 제3자 우위 확인 없음.", None),
    },
    "finda": {
        "traction": (4, "대출 비교·중개(유상거래 모델) 실운영, 시리즈C 규모 기업.", None),
        "team": (None, "이혜민·박홍민 이름과 투자사 인연만 있고 개인 이력 미특정.", None),
        "market": (None, "덱·시장 논증 문서 없어 상향 판정 불가.", None),
        "moat": (3, "대출 비교 데이터 자산 존재하나 제3자 우위 미확인.", None),
    },
    "comento": {
        "traction": (3, "300개+ 직무 라이브 교육 실운영(외부 사용)이나 매출·유료 등 돈이동 증거 없음.", None),
        "team": (None, "대표 이재성 이름만 있고 개인 이력 '상세 확인 필요'.", None),
        "market": (None, "덱·시장 논증 문서 없어 상향 판정 불가.", None),
        "moat": (3, "직무 콘텐츠 라이브러리 자산은 정의상 존재하나 우위 가시성 미확인.", None),
    },
    "dano": {
        "traction": (4, "설립 4년 만 매출 100억 명시(유료·우상향).", None),
        "team": (None, "정범윤·이지수 이름만 있고 개인 이력 '상세 확인 필요'.", None),
        "market": (None, "덱·시장 논증 문서 없어 상향 판정 불가.", None),
        "moat": (3, "콘텐츠·브랜드 자산 존재하나 제3자 우위 확인 없음.", None),
    },
    "quotabook": {
        "traction": (2, "B2B 캡테이블 SaaS로 계약·PO 등 금전적 증거 전무, 시드후기 이상 L2 상한.", None),
        "team": (3, "최동현 전 VC 투자심사역으로 관련 도메인·초기 창업.", 4),
        "market": (None, "덱·시장 논증 문서 없어 상향 판정 불가.", None),
        "moat": (3, "캡테이블 전환비용 자산 있으나 제3자 우위 미확인.", None),
    },
    "newneek": {
        "traction": (2, "뉴스레터 구독자는 있으나 유료·금전적 증거가 전혀 없음.", None),
        "team": (None, "포브스 30 Under 30은 수상일 뿐 개인 소속·직무·이력 미특정.", None),
        "market": (None, "덱·시장 논증 문서 없어 상향 판정 불가.", None),
        "moat": (3, "구독자 네트워크 자산 존재하나 우위 가시성 미확인.", None),
    },
    "saib": {
        "traction": (2, "제품 라인 서술만 있고 외부 사용·판매 사실이 명시되지 않음.", None),
        "team": (None, "대표 박지원 이름만 있고 개인 이력 '상세 확인 필요'.", None),
        "market": (None, "덱·시장 논증 문서 없어 상향 판정 불가.", None),
        "moat": (3, "식물성 무해성분 제품 차별화 주장은 보도되나 우위 미구축.", None),
    },
    "clozetshare": {
        "traction": (4, "누적 5만건 공유(유상 대여 거래)가 명시됨.", None),
        "team": (None, "창업자 '확인 필요'로 개인 경력 사실 없음.", None),
        "market": (None, "덱·시장 논증 문서 없어 상향 판정 불가.", None),
        "moat": (3, "공유 재고·거래 데이터 자산 존재하나 제3자 우위 미확인.", None),
    },
    "jaranda": {
        "traction": (3, "돌봄·교육 매칭 운영은 시사되나 거래액·매출 등 돈이동 명시가 없음.", 4),
        "team": (2, "장서정 대기업 근무·육아 경험뿐 돌봄 도메인 직접 경력이 약함.", 3),
        "market": (None, "덱·시장 논증 문서 없어 상향 판정 불가.", None),
        "moat": (3, "매칭 네트워크 자산 존재하나 제3자 우위 미확인.", None),
    },
    "opgg": {
        "traction": (4, "2019 매출 80억 명시(유료·우상향).", None),
        "team": (None, "창업자 '확인 필요'로 개인 경력 사실 없음.", None),
        "market": (None, "덱·시장 논증 문서 없어 상향 판정 불가.", None),
        "moat": (3, "전적검색 데이터 자산은 정의상 존재하나 우위 가시성의 제3자 확인 없음.", 4),
    },
    "payple": {
        "traction": (2, "'스트라이프 지향' 서술뿐이고 B2B 결제로 금전적 증거가 없어 L2 상한.", None),
        "team": (None, "대표 김현철 이름만 있고 개인 이력 '상세 확인 필요'.", None),
        "market": (None, "덱·시장 논증 문서 없어 상향 판정 불가.", None),
        "moat": (3, "결제 인프라 방어자산 주장뿐 제3자 우위 미확인.", None),
    },
    "divestudios": {
        "traction": (2, "제작 스튜디오 존재뿐이고 콘텐츠의 외부 사용·유료 사실이 명시되지 않음.", None),
        "team": (3, "형제 Eric Nam(K-팝 가수) 등 엔터 도메인 연결의 초기 창업.", 2),
        "market": (None, "덱·시장 논증 문서 없어 상향 판정 불가.", None),
        "moat": (3, "K-팝 스타 연계 네트워크 자산 존재하나 우위 가시성 미확인.", None),
    },
    "beluga": {
        "traction": (4, "'벨루가 비즈니스' 주류 도매유통(유상거래 모델) 실운영이 명시됨.", None),
        "team": (None, "대표 김상민 이름만 있고 개인 이력 '상세 확인 필요'.", None),
        "market": (None, "덱·시장 논증 문서 없어 상향 판정 불가.", None),
        "moat": (3, "도매유통 공급 네트워크 자산 존재하나 제3자 우위 미확인.", None),
    },
    "rarey": {
        "traction": (None, "프리시드로 외부 사용·유료 고객·출시 등 트랙션 사실이 문서에 없어 판정 불가", None),
        "team": (2, "대표가 서울대 로스쿨 출신으로 특정되나 뷰티·스타일 도메인 연결이 약함", None),
        "market": (None, "덱·시장 논증 문서 없이 보도의 뷰티테크 언급뿐이라 상향 판정 금지", None),
        "moat": (None, "얼굴형 분석 추천은 제품 서술일 뿐 데이터·IP 우위 주장이 문서에 없음", None),
    },
    "princeton_critical_minerals": {
        "trl": (3, "입주 시점 kiddie pool 규모 소형 프로토타입 테스트 단계로 통합·운용 실증 서술 없음(랩 프로토타입)", None),
        "team": (4, "환경공학 PhD·프린스턴 교수의 깊은 도메인이나 이전 스타트업 스케일업 이력 없음", None),
        "manufacturing": (None, "BOM 원가·공급사/CM·DFM 등 양산 경로 사실이 문서에 없음", None),
        "customer": (2, "기존 리튬 증발지 사업자라는 타깃 세그먼트만 정의(후행 칠레 파일럿 제외)", None),
    },
    "renovate_robotics": {
        "trl": (None, "로봇 'Rufus' 개발 서술뿐 프로토타입 동작·실증 사실이 없어 TRL 특정 불가", None),
        "team": (2, "COO가 전 SOSV/HAX Associate로 특정되나 건설 로보틱스 도메인 연결이 약하고 공동창업자 이력 불명", None),
        "manufacturing": (None, "양산 경로(BOM·공급사·DFM) 사실이 문서에 없음", None),
        "customer": (2, "단독주택 지붕·태양광 설치라는 타깃 세그먼트만 정의, 특정 고객·합의 없음", None),
    },
    "gaia_ai": {
        "trl": (3, "센서 백팩+앱 프로토타입은 있으나 파일럿은 입주 후 계획(상용화 이전)으로 실환경 실증 진행 서술 없음(랩 프로토타입)", None),
        "team": (None, "창업자 이력 확인 필요로 개인 경력 사실 없음", None),
        "manufacturing": (None, "양산 경로 사실이 문서에 없음", None),
        "customer": (3, "입주 시점 세계 최대 목재기업 3곳과 논의 진행 중(특정 상대방과 협의)", None),
    },
    "danu_robotics": {
        "trl": (4, "분당 40픽·오염률 1% 프로토타입에 Glasgow·포르투갈 실환경 파일럿이 진행 중(실증 진행)", None),
        "team": (3, "SW·제조 엔지니어의 관련 도메인 초기 창업, 스케일업·엑싯 이력 없음", None),
        "manufacturing": (None, "HW 판매하나 BOM·공급사·DFM 등 양산 경로 정량 사실이 문서에 없음", None),
        "customer": (5, "포르투갈 EGF 유료 파일럿 등 특정 고객 유료 파일럿 확보", None),
    },
    "rightbot": {
        "trl": (None, "자율 하역 로봇 서술뿐 프로토타입 동작·실증 사실이 없어 TRL 특정 불가", None),
        "team": (4, "공동창업자가 전 GreyOrange(물류 로보틱스)로 깊은 도메인이나 창업 스케일업·엑싯 이력 없음", None),
        "manufacturing": (None, "양산 경로 사실이 문서에 없음", None),
        "customer": (2, "트럭·컨테이너 하역이라는 세그먼트 정의, Amazon은 투자자이며 고객 합의 문서 없음(후행 인수 제외)", None),
    },
    "xera_energy": {
        "trl": (None, "데모데이 참여·기술 서술뿐 프로토타입 TRL 사실 없음(전시만으로 특정 금지)", None),
        "team": (None, "창업자 확인 필요로 개인 경력 사실 없음", None),
        "manufacturing": (None, "양산 경로 사실이 문서에 없음", None),
        "customer": (2, "폐쇄루프 캐소드 소재라는 배터리 제조 타깃 세그먼트만 정의", None),
    },
    "navion_energy": {
        "trl": (None, "데모데이 참여·개발 서술뿐 프로토타입 TRL 사실 없음", None),
        "team": (None, "창업자 확인 필요로 개인 경력 사실 없음", None),
        "manufacturing": (None, "양산 경로 사실이 문서에 없음", None),
        "customer": (2, "AI 데이터센터라는 타깃 세그먼트 정의, 특정 고객·합의 없음", None),
    },
    "terran_robotics": {
        "trl": (4, "케이블 구동 다짐 로봇으로 첫 인허가 주택 완공(실환경 통합 실증)이나 완료·범위 불명으로 보수 판정", 5),
        "team": (3, "AI·로보틱스+건설 배경의 관련 도메인 초기 창업, 스케일업·엑싯 이력 없음", None),
        "manufacturing": (None, "로봇 양산 경로(BOM·공급사·DFM) 사실이 문서에 없음", None),
        "customer": (2, "저비용 흙 주택이라는 세그먼트 정의(2025년 유상 빌드 계약은 입주 후 활동으로 제외)", None),
    },
    "sodex_innovations": {
        "trl": (4, "중장비 장착 레이저 스캐닝으로 건설·광산 현장 가동 중 측량(운용 환경 실증)이나 실증 완료 서술 불명", 5),
        "team": (3, "HTL 동문 3인의 학교 프로젝트 출발 관련 도메인 초기 창업, 스케일업 이력 없음", None),
        "manufacturing": (None, "양산 경로 사실이 문서에 없음", None),
        "customer": (2, "건설·광산 현장이라는 세그먼트 정의, 특정 고객 합의 문서 없음(후행 €4M 라운드 제외)", None),
    },
    "namu_robotics": {
        "trl": (4, "입주 시점 자율 식목 로봇 프로토타입·테스트 단계이나 정량 검증·통합 동작 서술 불명", 5),
        "team": (None, "공동창업자 이력 확인 필요로 개인 경력 사실 없음", None),
        "manufacturing": (None, "양산 경로 사실이 문서에 없음", None),
        "customer": (2, "조림·ESG 대상 세그먼트 정의(Rio Tinto는 투자자, 첫 상업 조림은 입주 후 계획)", None),
    },
    "benerg": {
        "trl": (None, "데모데이 참여·성능 주장뿐 프로토타입 TRL 사실 없음", None),
        "team": (None, "창업자 확인 필요로 개인 경력 사실 없음", None),
        "manufacturing": (None, "양산 경로 사실이 문서에 없음", None),
        "customer": (2, "건물 현장 오프그리드 전력이라는 타깃 세그먼트 정의", None),
    },
    "gemma_robotics": {
        "trl": (None, "데모데이 참여·컨셉 서술뿐 프로토타입 TRL 사실 없음", None),
        "team": (None, "CTO 이름뿐 이력 확인 필요로 개인 경력 사실 부족", None),
        "manufacturing": (None, "양산 경로 사실이 문서에 없음", None),
        "customer": (2, "일상 뷰티 소비자라는 타깃 세그먼트 정의", None),
    },
}
