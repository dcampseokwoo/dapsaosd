"""백테스트 데이터셋 — 웹 검색으로 수집한 14개사 팩트시트 + 레벨 분류.

수집 방법 및 한계
-----------------
이 환경은 네트워크 정책상 500.co / hax.co / sosv.com / wikipedia.org 등에 대한
직접 HTTP 접근이 차단된다(프록시 CONNECT 403). 따라서 페이지 크롤링이 아니라
**웹 검색 결과 본문**만으로 팩트를 수집했다. 결과적으로:

- 증거 등급의 `문서 명시`는 전부 **언론 보도/기업DB 표기**로 대체된다
  (피치덱·CV·설문은 존재하지 않음 → 전 기업이 프롬프트 정의상 `간이 진단` 대상).
- 합격 기업은 **합격 시점 이전 상태**로 평가하려 했으나, 검색으로 얻는 정보는
  현재 시점 정보가 섞인다 → 후행 정보 혼입(hindsight) 위험을 개별 주석에 표기.

정답(ground_truth)
------------------
- `admitted_500` : 디캠프–500글로벌 파트너십으로 실제 플래그십 참가 확정 (2025.09 보도)
- `admitted_hax` : HAX 프로그램 졸업/동문으로 SOSV·HAX 공식 채널에 명시
- `unknown`      : 디캠프 스타트업 DB 소속. 500/HAX 지원·합격 기록 미확인(불합격 아님)
- `probe`        : 게이트 동작 확인용으로 일부러 넣은 케이스
"""
from __future__ import annotations

from dataclasses import dataclass, field

from screening import rules


@dataclass
class Company:
    key: str
    name: str
    track: str                     # "500" | "hax" | "bio_routing"
    sector_key: str
    sector_note: str
    stage_band: str                # 프리시드 / 시드 초기 / 시드 후기 / A 이후 / 확인 필요
    ground_truth: str
    facts: list[tuple[str, str]]   # (사실, 증거등급)
    levels: dict[str, tuple[int | None, str]]   # 축 → (레벨 or None=확인필요, 근거)
    credibility: dict[str, str] = field(default_factory=dict)
    unstable: dict[str, int] = field(default_factory=dict)  # 경계 판정 축 → 대안 레벨
    needs_confirm: list[str] = field(default_factory=list)
    fit: str = "확인 필요"
    fit_reason: str = ""
    sources: list[str] = field(default_factory=list)
    note: str = ""
    # 게이트 입력
    has_working_product: bool = True
    product_note: str = ""
    fulltime_confirmed: bool = False
    relocation_confirmed: bool = False
    commitment_note: str = "설문 미제출 — 풀타임/리로케이션 의사 미확인"
    priced_round: bool = False
    cap_table_ok: bool = True
    cap_table_note: str = "캡테이블 미제출 — 지분 수용 가능성 미확인"
    english_ok: bool = False
    english_note: str = "덱/CV 미제출 — C레벨 영어 역량 미확인"

    @property
    def levels_only(self) -> dict[str, int | None]:
        return {a: v[0] for a, v in self.levels.items()}


CRED_OK, CRED_WARN = rules.CRED_OK, rules.CRED_WARN

# 신뢰성 스캔 5항목 — 원문 문서가 없어 대부분 '문서 미제출'로 판정 불가.
# 공개 정보만으로 확인 가능한 항목(고객 vs 위시리스트, 과장 표현)만 실제 판정.
_CRED_NO_DOC = {
    "교차 문서 수치 일관성": CRED_OK,      # 비교할 문서가 없어 모순 발견 불가
    "산술/환율 오류": CRED_OK,
    "자기인용": CRED_OK,
}


def _cred(customers: str, language: str) -> dict[str, str]:
    d = dict(_CRED_NO_DOC)
    d["고객 vs 위시리스트"] = customers
    d["과장 표현"] = language
    return d


COMPANIES: list[Company] = [
    # ================================================================ 500 합격군
    Company(
        key="cardmonster", name="카드몬스터 (CardMonster)", track="500",
        sector_key="games", sector_note="온·오프라인 게임 스튜디오 + AI 게임 제작 플랫폼",
        stage_band="시드 초기", ground_truth="admitted_500",
        facts=[
            ("2023.09 설립, 2026.03 기준 임직원 10명", "문서 명시(기업DB)"),
            ("2024.08 500 Global·매쉬업벤처스 프리시드 투자 유치", "문서 명시(보도)"),
            ("대표 손수현 — 넥슨·크래프톤(PUBG) 게임 기획/제작 경력", "문서 명시(보도)"),
            ("오프라인에서 게임을 검증한 뒤 온라인 전환하는 전략", "문서 명시(보도)"),
            ("AI로 카드 디자인·밸런싱·콘텐츠 확장·디지털 전환 자동화", "문서 명시(보도)"),
            ("MRR / 유료 사용자 수 / 성장률", "확인 필요"),
            ("2025.09 디캠프 추천으로 500 플래그십 참가 확정", "문서 명시(보도)"),
        ],
        levels={
            "traction": (2, "출시·유료화 증거 공개 없음. 오프라인 검증 단계 = 금전적 증거 없는 파일럿 → L2"),
            "team": (4, "넥슨·크래프톤 깊은 도메인 경력이나 스케일업/엑싯 이력 미확인 → L5 미만, L3 초과"),
            "market": (3, "글로벌 TCG/보드게임 시장은 크지만 상향식 $1B 논증 미확인 → L3"),
            "moat": (3, "AI 제작 파이프라인 + 오프라인 검증 루프는 그럴듯하나 구축 증거 없음 → L3"),
        },
        unstable={"team": 3, "traction": 1},
        credibility=_cred(CRED_OK, CRED_OK),
        needs_confirm=["MRR·유료 전환 지표", "풀타임 여부", "SF 리로케이션 의사", "캡테이블"],
        fit="높음",
        fit_reason="500 Global 이 직접 프리시드 투자한 기존 포트폴리오사 + 디캠프 추천 채널. 섹터 무관(sector-agnostic) 프로그램",
        sources=[
            "https://www.startuptoday.kr/news/articleView.html?idxno=49100",
            "https://platum.kr/archives/232349",
            "https://wowtale.net/2025/09/01/246287/",
            "https://thevc.kr/cardmonster",
        ],
        note="정답=합격. 후행 정보(합격 사실) 자체는 평가 입력에서 제외했다.",
        product_note="오프라인 게임 실물 출시·테스트 확인 → 동작하는 제품 존재",
    ),
    Company(
        key="allsale", name="올세일코퍼레이션 (Allsale)", track="500",
        sector_key="tech_enabled", sector_note="미국 틱톡샵 진출 원스톱 지원 + 인플루언서 마케팅 솔루션",
        stage_band="시드 초기", ground_truth="admitted_500",
        facts=[
            ("미국 틱톡샵 공식 파트너사", "문서 명시(보도)"),
            ("2024.08 CJ온스타일 전략적 투자 유치", "문서 명시(보도)"),
            ("중소 브랜드 대상 입점·물류·판매·마케팅 원스톱 체계 구축", "문서 명시(보도)"),
            ("대표 김정동", "문서 명시(기업DB)"),
            ("2025.09 디캠프 추천으로 500 플래그십 참가 확정 (최대 15억 투자 기회)", "문서 명시(보도)"),
            ("MRR / GMV / 유료 브랜드 수", "확인 필요"),
            ("라운드명(시드/프리A) 미공개 — 전략적 투자만 확인", "확인 필요"),
        ],
        levels={
            "traction": (None, "GMV·MRR·거래 브랜드 수 일체 미공개 → `확인 필요`"),
            "team": (3, "커머스·인플루언서 도메인 적합, 연쇄창업/엑싯 이력 미확인 → L3"),
            "market": (3, "미국 틱톡샵 GMV 는 대형이나 상향식 논증 미확인 → L3"),
            "moat": (4, "틱톡샵 '공식 파트너' 지위 + CJ온스타일 전략적 투자 = 이미 확보된 채널 우위 → L4"),
        },
        unstable={"moat": 3},
        credibility=_cred(CRED_OK, CRED_WARN),
        needs_confirm=["월 GMV·수수료 매출", "브랜드 리텐션", "틱톡샵 파트너 계약 증빙", "풀타임/리로케이션"],
        fit="높음",
        fit_reason="미국 시장 진출이 사업의 본질 = 실리콘밸리 4개월 프로그램과 정합. 500 의 커머스/마켓플레이스 트랙 레코드",
        sources=[
            "https://www.hankookilbo.com/News/Read/A2025083111480001980",
            "https://wowtale.net/2025/09/01/246287/",
            "https://thevc.kr/allsale",
        ],
        note="정답=합격. '공식 파트너사' 표현은 계약 증빙 미확인 → 과장 표현 경계 판정.",
        product_note="틱톡샵 운영 대행 서비스 실운영 중",
    ),
    # ================================================================ HAX 합격군
    Company(
        key="stillbright", name="Still Bright", track="hax",
        sector_key="materials", sector_note="전기화학 구리 정련(RACER 공정) — 소재/기후",
        stage_band="프리시드", ground_truth="admitted_hax",
        facts=[
            ("2022 설립, 컬럼비아대 연구 스핀아웃, 뉴어크 NJ 소재", "문서 명시(보도)"),
            ("공동창업 Randy Allen(CEO) / Jon Vardner(CTO) — 컬럼비아대 연구진", "문서 명시(보도)"),
            ("상온·상압 습식제련(바나듐 기반)으로 정련, 기존 대비 최대 90% 저비용 주장", "문서 명시(보도)"),
            ("HAX 입주(뉴어크 랩) 후 졸업 — SOSV 포트폴리오", "문서 명시(HAX 공식)"),
            ("[후행] 2025.07 시드 $18.7M (Material Impact·Breakthrough Energy 공동 리드)", "문서 명시(보도)"),
            ("[후행] 연 2톤 파일럿 → 2028년 500톤 실증 설비 목표", "문서 명시(보도)"),
        ],
        levels={
            "trl": (3, "HAX 입주 시점 = 대학 연구 기반 랩 프로토타입 → TRL 3~4 = L3"),
            "team": (4, "컬럼비아 박사급 전기화학 도메인 2인. 하드웨어 창업 스케일업 이력은 없음 → L4"),
            "manufacturing": (3, "상온·상압 = 설비 단순화라는 명확한 원가 논리. 입주 시점 BOM/CM 정량화 없음 → L3"),
            "customer": (1, "입주 시점 고객·유료 파일럿 없음 → L1"),
        },
        unstable={"trl": 4},
        credibility=_cred(CRED_OK, CRED_WARN),
        needs_confirm=["입주 시점 실제 TRL", "원가 90% 절감 주장의 산출 근거"],
        fit="높음",
        fit_reason="HAX 의 명시 테마(critical minerals·산업 독립·기후 하드웨어) 정면 일치. HAX 가 직접 홍보하는 대표 사례",
        sources=[
            "https://hax.co/still-bright-raises-18-7m-seed-round-to-slash-copper-costs/",
            "https://sosv.com/company/still-bright/",
            "https://www.finsmes.com/2025/08/still-bright-raises-18-7m-in-seed-funding-round/",
        ],
        note="정답=합격. [후행] 표시 사실은 레벨 분류에서 제외했다.",
        product_note="랩 스케일 공정 실증", english_ok=True,
        english_note="미국 법인·영어권 창업팀", cap_table_ok=True,
        cap_table_note="프리시드 — HAX 지분 수용 가능",
    ),
    Company(
        key="neptune", name="Neptune Robotics", track="hax",
        sector_key="robotics", sector_note="선체 청소 수중 로봇(RaaS) — 해양 탈탄소",
        stage_band="시드 초기", ground_truth="admitted_hax",
        facts=[
            ("Entrepreneur First 출신 팀, HAX 동문", "문서 명시(HAX 공식)"),
            ("AI 기반 생물부착 판별 + 캐비테이션 세정 수중 로봇", "문서 명시(보도)"),
            ("연료 절감·CO2 감축이라는 정량 가치 제안", "문서 명시(보도)"),
            ("[후행] Cargill 2022년부터 벌크선 도입, NYK 확대 계약", "문서 명시(보도)"),
            ("[후행] 누적 $69.4M, 시리즈B $52M (Granite Asia 리드), 로봇 27대 가동·50개 항만", "문서 명시(보도)"),
        ],
        levels={
            "trl": (4, "입주 시점 실해역에서 동작하는 통합 프로토타입 → TRL 5~6 = L4"),
            "team": (4, "EF 선발 기술 창업팀 + 로보틱스 도메인. 엑싯 이력 없음 → L4"),
            "manufacturing": (3, "로봇 자체 조립 + 서비스(RaaS) 모델로 양산 부담 회피. BOM 정량화 근거 없음 → L3"),
            "customer": (3, "입주 시점 선사 대상 실증/디스커버리 확인, 유료 디자인윈 증거는 미확인 → L3"),
        },
        unstable={"customer": 4},
        credibility=_cred(CRED_OK, CRED_OK),
        needs_confirm=["입주 시점 유료 파일럿 여부"],
        fit="높음",
        fit_reason="HAX 가 '10년간 로보틱스 최다 프리시드 투자자'로 자칭. 산업용 로봇 + 기후 = 테마 정면 일치",
        sources=[
            "https://hax.co/company/neptune-robotics/",
            "https://sosv.com/haxs-neptune-robotics-is-creating-an-army-of-underwater-robots-to-decarbonize-maritime-industry/",
            "https://www.marinetechnologynews.com/news/neptune-robotic-cleaning-maritime-653572",
        ],
        note="정답=합격. [후행] 표시 사실은 레벨 분류에서 제외했다.",
        product_note="실해역 운용 로봇", english_ok=True,
        english_note="홍콩 기반 영어권 팀", cap_table_note="프리시드/시드 — 수용 가능",
    ),
    # ================================================================ 디캠프 DB 대조군
    Company(
        key="safetics", name="세이프틱스", track="500",
        sector_key="pure_sw", sector_note="협동로봇 충돌 안전 분석 SW + 인증 서비스 (B2B)",
        stage_band="A 이후", ground_truth="unknown",
        facts=[
            ("2024.08 시리즈A 20억 (제이비인베스트먼트·어니스트벤처스)", "문서 명시(보도)"),
            ("매출 4.1억(2023) → 4.9억(2024) → 7.0억(2025), 2025 +43.2%", "문서 명시(기업DB)"),
            ("신규 솔루션 '기버' 첫 고객사 두산로보틱스 확보", "문서 명시(보도)"),
            ("2025.12 대만 넥스코봇과 해외 총판 계약 (대만·중국·일본 독점 공급)", "문서 명시(보도)"),
            ("MoM 성장률 / 계약당 ARR", "확인 필요"),
        ],
        levels={
            "traction": (4, "유료 고객 + 명확한 우상향(연 +43%). 단 ≥20% MoM 은 아님 → L5 미달, L4"),
            "team": (3, "로봇 안전 도메인 적합, 연쇄창업/엑싯 이력 미확인 → L3"),
            "market": (3, "협동로봇 안전 규제 시장은 성장하나 상향식 $1B 논증 미확인 → L3"),
            "moat": (4, "안전 인증·규격 기반 진입장벽 + 총판 락인 → L4"),
        },
        credibility=_cred(CRED_OK, CRED_OK),
        needs_confirm=["MoM 성장률", "총판 계약 최소구매 조건", "시리즈A 이후 잔여 런웨이"],
        fit="중간",
        fit_reason="제품·트랙션은 강하나 시리즈A 완료 = 플래그십(프리시드~시드) 스테이지 밴드 이탈. HAX 는 순수 SW 로 제외 섹터",
        sources=[
            "https://platum.kr/archives/232340",
            "https://www.mt.co.kr/future/2026/01/13/2026011309412050545",
            "https://thevc.kr/safetics",
        ],
        note="라우팅 검증용: 로봇 '관련' 기업이지만 산출물이 SW 라 HAX 제외 섹터 → 500 트랙.",
        product_note="상용 판매 중인 SW 제품", priced_round=True,
    ),
    Company(
        key="dhive", name="디하이브", track="hax",
        sector_key="robotics", sector_note="자율주행 방범·물류 로봇 '로바' + 로보파일럿 관제",
        stage_band="시드 초기", ground_truth="unknown",
        facts=[
            ("THE VC 기준 투자 2건, 최근 단계 Seed", "문서 명시(기업DB)"),
            ("수원시 자율주행 방범·물류 서비스 단계적 도입 예정", "문서 명시(보도)"),
            ("국토부 지역주도형 스마트도시 규제샌드박스 선정, 국비 5억 지원", "문서 명시(보도)"),
            ("창업팀 구성·경력", "확인 필요"),
            ("BOM·양산 파트너·매출", "확인 필요"),
        ],
        levels={
            "trl": (4, "지자체 실증에 투입되는 동작 로봇 → 실환경 검증 = L4"),
            "team": (None, "창업자 경력·하드웨어 이력 공개 정보 없음 → `확인 필요`"),
            "manufacturing": (None, "BOM·CM·DFM 언급 전무 → `확인 필요`"),
            "customer": (3, "지자체 실증 + 국비 과제. 상업 유료 계약 증거 없음 → L3"),
        },
        credibility=_cred(CRED_WARN, CRED_OK),
        needs_confirm=["수원시 건이 유상 계약인지 국비 과제인지", "창업팀 하드웨어 경력", "양산 원가"],
        fit="낮음",
        fit_reason="국비·규제샌드박스 중심의 정부과제 그래머. 지자체 조달은 세일즈 사이클이 4개월 프로그램과 불일치",
        sources=["https://thevc.kr/dhive", "https://thevc.kr/dhive/fundings"],
        note="`확인 필요` 축이 2개 — strict/neutral 모드 간 판정이 가장 크게 갈리는 케이스.",
        product_note="실증 투입 로봇 존재",
    ),
    Company(
        key="bitbyte", name="비트바이트", track="500",
        sector_key="pure_sw", sector_note="플레이키보드 / 앱테크 '돈이돼지' — 광고 수익화 앱",
        stage_band="시드 후기", ground_truth="unknown",
        facts=[
            ("2023.02 딜라이트룸 전략적 투자(라운드명 미공개), 누적 약 21.4억", "문서 명시(보도)"),
            ("2026.02 '돈이돼지' 출시, 4~5월 연속 흑자·월간 BEP 달성", "문서 명시(보도)"),
            ("딜라이트룸 광고 수익화 솔루션 '다로' 적용으로 매출 전년 동기 대비 8배", "문서 명시(보도)"),
            ("대표 안서형", "문서 명시(보도)"),
            ("절대 매출 규모·MAU", "확인 필요"),
        ],
        levels={
            "traction": (4, "전년비 8배(월 환산 약 19% MoM) + 월간 BEP. ≥20% MoM '지속' 근거는 미확인 → L4"),
            "team": (3, "앱 프로덕트 도메인 적합, 글로벌 스케일업 이력 미확인 → L3"),
            "market": (3, "모바일 광고 수익화 시장은 크나 앱테크 세그먼트의 상향식 논증 없음 → L3"),
            "moat": (2, "성장 동력이 투자사(딜라이트룸)의 '다로' 솔루션에 의존 — 자체 방어자산 아님 → L2"),
        },
        unstable={"traction": 5},
        credibility=_cred(CRED_OK, CRED_WARN),
        needs_confirm=["절대 매출액", "다로 의존도/계약 조건", "8배 성장의 기저 규모"],
        fit="중간",
        fit_reason="VC 트랙 + 빠른 성장률은 프로그램과 정합하나, 국내 광고 아비트라지 성격이라 글로벌 확장 논거가 약함",
        sources=[
            "https://zdnet.co.kr/view/?no=20250724085612",
            "https://platum.kr/archives/264354",
            "https://thevc.kr/bitbyte",
        ],
        note="'8배 성장'은 기저 규모 미공개 — 과장 표현 경계.",
        product_note="앱 출시·수익화 중",
    ),
    Company(
        key="nthing", name="엔씽", track="hax",
        sector_key="agtech_hw", sector_note="모듈형 컨테이너 수직농장 '큐브' — 하드웨어",
        stage_band="A 이후", ground_truth="unknown",
        facts=[
            ("시리즈C까지 누적 투자 381억원 이상 (2025.04 기준)", "문서 명시(보도)"),
            ("2026.03 삼성벤처투자 전략적 투자 유치", "문서 명시(보도)"),
            ("중동(UAE) 등 해외 프로젝트 수주 이력", "추정"),
        ],
        levels={
            "trl": (5, "상용 배치된 컨테이너 농장 = 실환경 검증 완료 → L5"),
            "team": (4, "농업 하드웨어 도메인 + 다수 라운드 조달 실적 → L4"),
            "manufacturing": (4, "모듈 양산·설치 실적 존재. 공개 BOM 모델은 미확인 → L4"),
            "customer": (4, "실제 매출 고객 존재 → L4"),
        },
        credibility=_cred(CRED_OK, CRED_OK),
        needs_confirm=[],
        fit="낮음",
        fit_reason="품질과 무관하게 시리즈C = 프리시드 프로그램 대상 아님. HAX 조건(캡 없는 SAFE)과 정면 충돌",
        sources=["https://www.asiatime.co.kr/article/20250425500001", "https://thevc.kr/nthing"],
        note="게이트 검증용: 좋은 회사 × 스테이지 이탈 → 게이트에서 걸러져야 정상.",
        product_note="상용 제품 배치 중", priced_round=True, cap_table_ok=False,
        cap_table_note="시리즈C 캡테이블 — HAX 10% 수용 불가",
    ),
    Company(
        key="jobis", name="자비스앤빌런즈 (삼쩜삼)", track="hax",
        sector_key="fintech", sector_note="세금 환급 서비스 '삼쩜삼' — 핀테크 SW",
        stage_band="A 이후", ground_truth="probe",
        facts=[
            ("2022.03 시리즈C 300억, 이후 신규 라운드 없음", "문서 명시(보도)"),
            ("1,500억 규모 프리IPO 추진 중", "문서 명시(보도)"),
        ],
        levels={
            "trl": (1, "하드웨어 아님 — TRL 축 자체가 적용 불가"),
            "team": (4, "대규모 조달·상용 서비스 운영 실적 → L4"),
            "manufacturing": (1, "양산 개념 없음"),
            "customer": (5, "대규모 유료 사용자 기반"),
        },
        credibility=_cred(CRED_OK, CRED_OK),
        needs_confirm=[],
        fit="낮음",
        fit_reason="HAX 제외 섹터(핀테크) + 프리IPO 단계",
        sources=["https://thevc.kr/jobis"],
        note="게이트 검증용: HAX 제외 섹터가 실제로 탈락 처리되는지 확인.",
        product_note="상용 서비스", priced_round=True, cap_table_ok=False,
        cap_table_note="시리즈C/프리IPO — 수용 불가",
    ),
    Company(
        key="bredis", name="브레디스헬스케어", track="bio_routing",
        sector_key="bio", sector_note="체외진단/바이오 — 프롬프트 Step 3 라우팅 대상",
        stage_band="시드 초기", ground_truth="probe",
        facts=[
            ("2023.05 카이스트청년창업투자지주 등 시드", "문서 명시(기업DB)"),
            ("2023.08~09 디캠프 등 브릿지 유치, 이후 신규 라운드 없음", "문서 명시(기업DB)"),
        ],
        levels={},
        credibility={},
        needs_confirm=[],
        fit="해당 없음",
        fit_reason="바이오 → 점수 산출 금지, SOSV IndieBio NY/SF 안내",
        sources=["https://thevc.kr/bredishealthcare"],
        note="라우팅 검증용: 점수를 매기지 않고 IndieBio 로 넘겨야 정상.",
    ),
    Company(
        key="palussmny", name="팔루썸니 (김박사넷)", track="500",
        sector_key="pure_sw", sector_note="대학원 연구실 평판 커뮤니티 / 이공계 채용",
        stage_band="확인 필요", ground_truth="unknown",
        facts=[
            ("공개된 투자 라운드 정보 없음", "확인 필요"),
            ("매출·MAU·유료 고객", "확인 필요"),
            ("창업팀 경력", "확인 필요"),
        ],
        levels={
            "traction": (None, "매출·유료 고객 공개 정보 전무 → `확인 필요`"),
            "team": (None, "창업팀 정보 미확인 → `확인 필요`"),
            "market": (2, "국내 대학원생 커뮤니티 = 세그먼트 협소, 채용으로의 확장 논거 미확인 → L2"),
            "moat": (3, "연구실 평판 데이터는 축적형 네트워크 자산이나 수익화 연결 미확인 → L3"),
        },
        credibility=_cred(CRED_OK, CRED_OK),
        needs_confirm=["법인 실체·투자 이력", "매출 모델", "창업팀"],
        fit="낮음",
        fit_reason="국내 특화 커뮤니티 — 글로벌 스케일 그래머 부재",
        sources=["https://thevc.kr/phdkim"],
        note="정보 부족 케이스 — `간이 진단` 동작 확인용.",
        product_note="서비스 운영 중",
    ),
    Company(
        key="wavedeck", name="웨이브덱", track="500",
        sector_key="tech_enabled", sector_note="확인 필요 — 공개 정보에서 사업 내용 특정 실패",
        stage_band="시드 초기", ground_truth="unknown",
        facts=[
            ("2025년경 2억 규모 시드 투자 유치, 이후 라운드 없음", "문서 명시(기업DB)"),
            ("제품·매출·팀 일체", "확인 필요"),
        ],
        levels={
            "traction": (None, "공개 정보 없음"),
            "team": (None, "공개 정보 없음"),
            "market": (None, "사업 영역 특정 불가"),
            "moat": (None, "공개 정보 없음"),
        },
        credibility={},
        needs_confirm=["사업 내용", "제품 단계", "팀", "매출"],
        fit="확인 필요",
        fit_reason="정보 부족 — Fit 판정 불가",
        sources=["https://thevc.kr/"],
        note="전 축 `확인 필요` — neutral 모드에서 '판정 불가'가 나와야 정상.",
        has_working_product=False,
        product_note="프로토타입 존재 여부 확인 불가",
    ),
    Company(
        key="aroundus", name="어라운드어스", track="500",
        sector_key="tech_enabled", sector_note="지역 기반 서비스 (2019 시드 이후 공개 활동 확인 안 됨)",
        stage_band="시드 후기", ground_truth="unknown",
        facts=[
            ("2019.07 신한캐피탈·디캠프 등 시드 8.8억 유치", "문서 명시(보도)"),
            ("이후 7년간 신규 라운드·보도 없음", "문서 명시(기업DB)"),
            ("현재 매출·운영 상태", "확인 필요"),
        ],
        levels={
            "traction": (None, "최근 실적 정보 없음 — 활동 여부 자체가 미확인"),
            "team": (None, "현재 팀 구성 미확인"),
            "market": (2, "지역 기반 서비스 — 확장 논거 미확인 → L2"),
            "moat": (1, "7년간 축적된 방어자산의 증거 없음 → L1"),
        },
        credibility=_cred(CRED_OK, CRED_OK),
        needs_confirm=["법인 존속·운영 여부", "현재 매출", "팀 잔존 여부"],
        fit="낮음",
        fit_reason="시드 이후 7년 정체 — 4개월 급성장 프로그램 구조와 불일치",
        sources=["https://thevc.kr/aroundus"],
        note="정체 기업 검출 케이스.",
    ),
    Company(
        key="kkureogi", name="꾸러기수비대", track="hax",
        sector_key="unknown_hw", sector_note="확인 필요 — CES 2025 참가 외 사업 내용 특정 실패",
        stage_band="시드 초기", ground_truth="unknown",
        facts=[
            ("시드 10억 (BNK부산은행·AC패스파인더·KDB캐피탈 등)", "문서 명시(기업DB)"),
            ("CES 2025 참가", "문서 명시(기업DB)"),
            ("제품·기술·팀·매출", "확인 필요"),
        ],
        levels={
            "trl": (None, "CES 전시 = 프로토타입 시사이나 TRL 특정 불가"),
            "team": (None, "공개 정보 없음"),
            "manufacturing": (None, "공개 정보 없음"),
            "customer": (None, "공개 정보 없음"),
        },
        credibility={},
        needs_confirm=["제품 정의", "TRL", "팀", "고객"],
        fit="낮음",
        fit_reason="지역은행·정책금융 중심 조달 그래머. 글로벌 VC 트랙 신호 부재",
        sources=["https://thevc.kr/"],
        note="전 축 `확인 필요` — CES 참가만으로 레벨을 올리지 않는지 확인용.",
        has_working_product=True,
        product_note="CES 전시 = 프로토타입 존재 추정",
    ),
]


# ---------------------------------------------------------------- v2 재분류
# rules_v2 의 두 규칙에 따라 같은 사실을 다시 분류한 것:
#   (1) 주축(Traction/TRL)은 스테이지 밴드별 레벨표로 판정
#   (2) `문서 명시` 이상 증거가 없으면 레벨을 매기지 않는다(None)
#       — v1 에서 정보 부재를 L1 또는 '중간값 L3'로 흡수하던 것을 금지
LEVELS_V2: dict[str, dict[str, tuple[int | None, str]]] = {
    "cardmonster": {
        "traction": (3, "오프라인 게임 검증 = 외부 사용자 존재. 시드 초기 밴드표 L3(유료 증거는 미확인)"),
        "team": (4, "넥슨·크래프톤 경력 보도 명시 → 레벨 부여 가능"),
        "market": (None, "덱 미제출 — 시장 논증의 질을 평가할 근거 자체가 없음"),
        "moat": (3, "AI 제작 파이프라인 보도 명시, 구축 증거 없음 → L3"),
    },
    "allsale": {
        "traction": (4, "브랜드 대상 유상 운영대행 실운영 + 틱톡샵 공식 파트너 → 유료 고객 존재. 규모는 미확인"),
        "team": (None, "대표 성명 외 경력 미확인"),
        "market": (None, "덱 미제출 — 상향식 논증 평가 불가"),
        "moat": (4, "틱톡샵 공식 파트너 지위 = 확보된 채널 우위(보도 명시)"),
    },
    "stillbright": {
        "trl": (3, "프리시드 밴드표: 핵심 원리 실증(TRL 3) → L3"),
        "team": (4, "컬럼비아 박사급 전기화학 2인 보도 명시"),
        "manufacturing": (3, "상온·상압 = 설비 단순화 논리 명시. BOM/CM 정량화 없음"),
        "customer": (None, "고객 활동에 대한 공개 정보 부재 — '없음'이 아니라 '미확인'"),
    },
    "neptune": {
        "trl": (4, "시드 초기 밴드표: 실환경 실증 진행 중 → L4"),
        "team": (4, "EF 선발 기술 창업팀, 로보틱스 도메인 명시"),
        "manufacturing": (3, "RaaS 로 양산 부담 회피. BOM 정량화 근거 없음"),
        "customer": (3, "선사 대상 실증 = 구체적 고객 디스커버리 확인"),
    },
    "safetics": {
        "traction": (4, "A 이후 밴드표: 유료 고객 + 명확한 우상향(연 +43%). 20% MoM 아님"),
        "team": (None, "창업자 이력 미확인 — 사업 설명은 팀 근거가 아님"),
        "market": (None, "덱 미제출"),
        "moat": (4, "안전 인증 기반 진입장벽 + 총판 계약 보도 명시"),
    },
    "dhive": {
        "trl": (4, "시드 초기 밴드표: 지자체 실증 투입 = 실환경 실증 진행 중"),
        "team": (None, "창업팀 정보 없음"),
        "manufacturing": (None, "BOM·CM·DFM 언급 전무"),
        "customer": (3, "지자체 실증 = 구체적 고객 디스커버리"),
    },
    "bitbyte": {
        "traction": (4, "시드 후기 밴드표: 유료(광고) 매출 + 8배 성장·월 BEP = 명확한 우상향"),
        "team": (3, "플레이키보드 창업·운영 이력 보도 명시, 글로벌 스케일업 이력 없음"),
        "market": (None, "덱 미제출"),
        "moat": (2, "성장 동력이 투자사 솔루션(다로)에 의존 — 보도로 확인된 사실"),
    },
    "nthing": {
        "trl": (5, "A 이후 밴드표: 상용 배치·양산 검증"),
        "team": (4, "다수 라운드 조달·해외 프로젝트 실적"),
        "manufacturing": (4, "모듈 양산·설치 실적 존재"),
        "customer": (4, "매출 고객 존재"),
    },
    "jobis": {
        "trl": (None, "하드웨어 아님 — TRL 축 적용 불가(v1 처럼 L1 로 강등하지 않는다)"),
        "team": (4, "대규모 조달·상용 서비스 운영"),
        "manufacturing": (None, "양산 개념 없음 — 축 적용 불가"),
        "customer": (5, "대규모 유료 사용자"),
    },
    "palussmny": {
        "traction": (None, "매출·사용자 지표 전무"),
        "team": (None, "창업팀 미확인"),
        "market": (2, "국내 대학원생 커뮤니티 = 세그먼트 협소(서비스 정의로 확인 가능)"),
        "moat": (None, "데이터 자산의 수익화 연결 미확인"),
    },
    "wavedeck": {
        "traction": (None, "정보 없음"), "team": (None, "정보 없음"),
        "market": (None, "사업 영역 특정 불가"), "moat": (None, "정보 없음"),
    },
    "aroundus": {
        "traction": (None, "최근 실적 정보 없음 — 활동 여부 자체가 미확인"),
        "team": (None, "현재 팀 구성 미확인"),
        "market": (2, "지역 기반 서비스 — 확장 논거 미확인"),
        "moat": (None, "7년 공백 — 방어자산 유무를 판단할 근거 없음(L1 단정 금지)"),
    },
    "kkureogi": {
        "trl": (None, "CES 전시만으로 TRL 특정 불가"), "team": (None, "정보 없음"),
        "manufacturing": (None, "정보 없음"), "customer": (None, "정보 없음"),
    },
}


# ---------------------------------------------------------------- Fit 신호
# rules_v2.FIT_SIGNALS 의 6개 신호를 기업별로 yes/no/unknown 으로 분류.
# 근거 없는 항목은 반드시 unknown — 여기서도 '모르는 것'을 no 로 바꾸지 않는다.
FIT: dict[str, dict[str, str]] = {
    "cardmonster": {
        "stage_band_fit": "yes",          # 시드 초기
        "sector_theme_match": "no",       # 게임 스튜디오는 500 공개 주력 섹터 아님
        "similar_admitted_case": "yes",   # 500 Global 이 직접 프리시드 투자
        "vc_track_grammar": "yes",        # 500·매쉬업벤처스
        "sales_cycle_fit": "yes",         # B2C 게임 — 빠른 출시·성장 사이클
        "momentum": "yes",                # 2024.08 라운드, 2026 인원 10명
    },
    "allsale": {
        "stage_band_fit": "yes",
        "sector_theme_match": "unknown",  # Step 6.5 실패 — 500 커머스 테마 확인 불가
        "similar_admitted_case": "unknown",
        "vc_track_grammar": "yes",        # CJ온스타일 전략적 투자
        "sales_cycle_fit": "yes",         # 미국 진출이 사업의 본질
        "momentum": "yes",
    },
    "stillbright": {
        "stage_band_fit": "yes", "sector_theme_match": "yes",
        "similar_admitted_case": "yes", "vc_track_grammar": "yes",
        "sales_cycle_fit": "yes",        # HAX 는 성장 프로그램이 아니라 개발 프로그램
        "momentum": "yes",
    },
    "neptune": {
        "stage_band_fit": "yes", "sector_theme_match": "yes",
        "similar_admitted_case": "yes", "vc_track_grammar": "yes",
        "sales_cycle_fit": "yes", "momentum": "yes",
    },
    "safetics": {
        "stage_band_fit": "no",           # 시리즈A 완료
        "sector_theme_match": "yes",      # B2B SW — 500 주력 섹터
        "similar_admitted_case": "unknown",
        "vc_track_grammar": "yes",
        "sales_cycle_fit": "no",          # 엔터프라이즈 안전 인증 = 긴 사이클
        "momentum": "yes",
    },
    "dhive": {
        "stage_band_fit": "yes",
        "sector_theme_match": "yes",      # 로보틱스 = HAX 최다 투자 분야
        "similar_admitted_case": "yes",
        "vc_track_grammar": "no",         # 국비·규제샌드박스 중심
        "sales_cycle_fit": "no",          # 지자체 조달
        "momentum": "yes",
    },
    "bitbyte": {
        "stage_band_fit": "yes", "sector_theme_match": "yes",
        "similar_admitted_case": "unknown", "vc_track_grammar": "yes",
        "sales_cycle_fit": "yes", "momentum": "yes",
    },
    "nthing": {
        "stage_band_fit": "no", "sector_theme_match": "yes",
        "similar_admitted_case": "yes", "vc_track_grammar": "yes",
        "sales_cycle_fit": "no", "momentum": "yes",
    },
    "jobis": {
        "stage_band_fit": "no", "sector_theme_match": "no",
        "similar_admitted_case": "no", "vc_track_grammar": "yes",
        "sales_cycle_fit": "unknown", "momentum": "yes",
    },
    "palussmny": {
        "stage_band_fit": "unknown", "sector_theme_match": "unknown",
        "similar_admitted_case": "unknown",
        "vc_track_grammar": "no",         # 공개 라운드 없음 — VC 트랙 신호 부재
        "sales_cycle_fit": "unknown",
        "momentum": "no",                 # 최근 24개월 신호 없음
    },
    "wavedeck": {
        "stage_band_fit": "yes", "sector_theme_match": "unknown",
        "similar_admitted_case": "unknown", "vc_track_grammar": "yes",
        "sales_cycle_fit": "unknown", "momentum": "yes",
    },
    "aroundus": {
        "stage_band_fit": "yes", "sector_theme_match": "unknown",
        "similar_admitted_case": "unknown",
        "vc_track_grammar": "yes",        # 신한캐피탈·디캠프 (2019)
        "sales_cycle_fit": "unknown",
        "momentum": "no",                 # 7년 공백
    },
    "kkureogi": {
        "stage_band_fit": "yes", "sector_theme_match": "unknown",
        "similar_admitted_case": "unknown",
        "vc_track_grammar": "no",         # 지역은행·정책금융 중심
        "sales_cycle_fit": "unknown",
        "momentum": "yes",                # CES 2025
    },
}


def levels_v2_of(c: Company) -> dict[str, int | None]:
    return {a: v[0] for a, v in LEVELS_V2.get(c.key, {}).items()}


def by_key(key: str) -> Company:
    for c in COMPANIES:
        if c.key == key:
            return c
    raise KeyError(key)
