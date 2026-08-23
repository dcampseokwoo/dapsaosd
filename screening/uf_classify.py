"""US FORGED — §1 소개문 기반 하드테크 분류 (LLM, 캐시 우선).

업종 라벨 화이트리스트를 폐기하고 **1줄 사업 소개**를 1차 판정 근거로 삼는다. 업종·기술은
프롬프트에 보조 신호로만 첨부하고 사전 필터링에 쓰지 않는다(감사 결함의 뿌리).

실행: 캐시 우선(A). 분류는 LLM(이 세션의 Claude/서브에이전트)이 1회 수행해 캐시에
고정하고, 엔진은 캐시를 결정적으로 읽는다. 캐시 키 = 사업자번호 + 소개문 해시 +
모델명 + 프롬프트 버전 (프롬프트를 고치면 옛 판정이 자동 무효화되게).

분류 순서(파이프라인): 배제(§4) → 스테이지(§3) → **LLM 분류(첫 하드테크 판정)**.
Pre-A 는 스테이지에서 '예외 후보'로만 들어오고, 분류의 physical_product 로 최종 확정한다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "cache" / "classification.json"

MODEL = "claude-agent"        # 분류 수행 모델(캐시 키 구성). 런타임 API 붙이면 실제 id 로.
PROMPT_VERSION = "v4"          # v4: OEM 소비재완제품 수탁=consumer(산업부품 OEM 제외) + 용도 축(화장품·미용 소재/기기=consumer)
#   v3: 코스메틱/뷰티 기본값 명시 + matched_program_field enum 강제
#   v2: 수직계열화 규칙 + consumer_facing_end_product·maturity_signal 필드

PROGRAM_FIELDS = [
    "Robotics/Automation", "Advanced Manufacturing", "Energy/Climate Tech",
    "Industrial Hardware", "Semiconductor/Advanced Materials", "Sensor/Edge Device",
    "Physical AI", "Healthtech Device", "Manufacturing Process Innovation",
    "Aerospace", "Quantum", "Other Deeptech", "None",
]
VERDICTS = ("hardtech", "software_only", "consumer", "not_a_startup", "unclear")

# ── 분류 프롬프트(전문). 사용자 검토 대상. ────────────────────────────────
PROMPT = """당신은 디캠프 x HAX 'US FORGED' Hardtech Pre-Program 지원 후보를 1차 분류하는
심사 보조자다. 목표는 "선발"이 아니라 **명백히 부적합한 기업을 배제**하는 것이다.

■ 핵심 판정 질문
이 기업이 **미국 고객에게 팔 수 있는 물리적 하드웨어·소재·장비·디바이스를 직접
설계하거나 제조하는가?**  판단은 '업종 라벨'이 아니라 '1줄 사업 소개'의 실체로 한다.
(업종·기술 라벨은 참고용 보조 신호일 뿐, 라벨만으로 판정하지 말 것.)

■ verdict 값 (하나만)
- hardtech      : 물리적 제품(하드웨어·소재·장비·디바이스)을 **직접 설계/제조**하는 것이
                  사업의 핵심. 하드웨어를 만들고 SW/데이터 구독을 얹은 형태도 hardtech.
- software_only : SW/앱/플랫폼으로 하드웨어를 제어·최적화·분석·중개만. 직접 제조 안 함.
- consumer      : 일반 소비재(화장품·식품·의류·숙박·유통 소비재 등).
- not_a_startup : 투자목적회사·조합·해외법인 등 사업 실체가 스타트업이 아님(신호가 소개에
                  드러날 때만; 법인격 배제는 별도 규칙이 담당하므로 확신 없으면 쓰지 말 것).
- unclear       : 소개문만으로 '직접 설계/제조'가 불확실. 아래 경계형이 대표적.

■ 핵심 규칙 — "기술 스택의 어느 층을 직접 소유하는가"
소재·부품·공정을 **자체 개발하거나 수직계열화**하면 hardtech. 완제품 **조립·수탁 생산만**
(자체 소재·부품·공정 차별성 없이) 하면 consumer 또는 unclear.
**최종 제품이 소비자용인지는 기준이 아니다** — 소비자용 완제품이라도 핵심 소재·부품·공정을
자체 개발하면 hardtech 로 하고 consumer_facing_end_product=true 로 표시한다.
  예: "압전세라믹 원료·트랜스듀서·구동회로 수직계열화" → hardtech (뷰티 완제품이어도).
      "초음파·이온토포레시스 등 기존 기술을 조합한 스킨케어 기기" → consumer(범용 조합).
  **화장품·뷰티·스킨케어 기본값(위 원칙의 명시):** 뷰티/화장품/스킨케어 완제품은 소개문에
  핵심 소재·부품·공정을 자체 개발/수직계열화한다는 **명시가 없으면 consumer 가 기본값**이다.
  (에코디엠랩은 '압전세라믹부터 완제품까지 자체 생산' 명시가 있어 hardtech. 그런 명시가
  없는 화장품 제조사는 '제조'라는 단어가 있어도 consumer.)

  **v4 — 수직계열화 원칙에 '용도 축' 명시(새 규칙 아님, 구체화):**
  (1) OEM/ODM 수탁: **소비재 완제품(화장품·오디오·생활용품 등)을 수탁 제조**하면
      사용 기술(bio-cellulose 등) 언급이 있어도 consumer(자체 제품이 아니라 수탁).
      **단, 산업용 부품·소재·장비를 OEM 납품하는 것은 해당하지 않는다**(부품업체엔 당연).
      예: 크레신(오디오 완제품 ODM)=consumer / 선진정공(산업 구조부품 OEM)=hardtech 유지.
  (2) 용도 축: 소재·부품·기기의 **최종 용도가 화장품·미용·에스테틱·이너뷰티**이면,
      **산업용 또는 임상 의료용 용도가 함께 명시되지 않는 한 consumer**(공고 Advanced
      Materials=산업용 소재, 화장품 원료는 '일반 소비재' 배제). 예: 아이엔지알(식물줄기세포
      뷰티 원료)=consumer / 시선테라퓨틱스(PNA 유전자치료제=임상 의료)=hardtech 유지.
      판단이 갈리면 배제하지 말고 consumer_facing=true 로 두어 T2 강등.

■ 경계형 처리 (감사에서 판단 유보됐던 유형 — 여기서 일관성이 드러난다)
1) 파운드리·수탁제조(남의 설계를 위탁생산, 자체 제품/IP 언급 없음)
   → 자체 기술 차별성이 소개에 없으면 unclear(수탁제조 의심), confidence 낮게. 자체 제품·
     독자 공정이 명시되면 hardtech.
2) 소재 상사·무역·유통(소재를 다루지만 직접 제조가 아니라 유통) → physical_product=false,
   verdict unclear(직접 제조 아님, 유통).
3) 연구용역·엔지니어링 컨설팅(하드웨어를 다루지만 자체 제품 없음, 용역 제공) → unclear.
4) 하드웨어 + SaaS 결합(센서·디바이스를 직접 만들어 팔고 데이터 구독을 붙임) → hardtech.
5) 기성 부품 제조 중소기업(범용 부품을 오래 만들어온 제조업체 느낌) → 물리적 제조는
   맞으므로 verdict 는 hardtech 로 둔다(배제하지 않는다). 대신 소개문 단서(범용 부품 다품목·
   OEM 납품·기술 차별성 주장 없음)를 maturity_signal 에 짧게 적는다. 이건 배제가 아니라
   우선순위 정렬용이고, 스타트업 여부 최종 확인은 설문이 한다.

■ physical_product (boolean)
물리적 제품을 **직접 설계·제조**하면 true. 유통·중개·용역·순수 SW 면 false.

■ consumer_facing_end_product (boolean)
최종 제품이 소비자용이면 true(hardtech 이어도 사람이 보게 표시). B2B 부품·장비·소재면 false.

■ maturity_signal (string)
소개에 '기성/성숙 제조업체' 단서(범용 부품 다품목·OEM 납품·기술 차별성 주장 없음)가 있으면
그 단서를 짧게 인용/기록. 없으면 "". (배제가 아니라 정렬용.)

■ 출력: 아래 JSON 스키마 정확히. evidence 는 판정 근거가 된 **소개문 구절을 원문 그대로
인용**(요약·창작 금지). matched_program_field 는 **반드시 아래 목록의 문자열 그대로** 쓴다
(자유 표기 금지): Robotics/Automation | Advanced Manufacturing | Energy/Climate Tech |
Industrial Hardware | Semiconductor/Advanced Materials | Sensor/Edge Device | Physical AI |
Healthtech Device | Manufacturing Process Innovation | Aerospace | Quantum | Other Deeptech |
None. 딱 맞는 게 없어도 가장 가까운 것을 고르고, 정말 없을 때만 Other Deeptech.

{
  "biz_no": "<입력 그대로>",
  "verdict": "hardtech|software_only|consumer|not_a_startup|unclear",
  "matched_program_field": "<위 목록 중 하나>",
  "physical_product": true|false,
  "consumer_facing_end_product": true|false,
  "maturity_signal": "<단서 or 빈 문자열>",
  "evidence": "<소개문 원문 인용>",
  "confidence": "high|medium|low"
}
"""


import re as _re

# 분류기가 자유 표기한 matched_program_field 를 공고 11개 분야로 정규화
_FIELD_MAP = [
    (r"robot", "Robotics/Automation"),
    (r"physical\s*ai|embodied", "Physical AI"),
    (r"aero|space|위성|우주|drone|satellite", "Aerospace"),
    (r"quantum|양자", "Quantum"),
    (r"semic|반도체|wafer|chip|photonic", "Semiconductor/Advanced Materials"),
    (r"material|소재|ceramic|세라믹|chemical|biomaterial|나노|nano", "Semiconductor/Advanced Materials"),
    (r"sensor|센서|iot|계측|측정|lidar|라이다", "Sensor/Edge Device"),
    (r"medical|헬스|health|의료|바이오\s*디바이스|wearable|진단|cgm|임플란트", "Healthtech Device"),
    (r"energy|배터리|batter|수소|hydrogen|태양|solar|climate|기후|탄소|carbon|ess|전지|storage", "Energy/Climate Tech"),
    (r"manufactur|제조|양산|공정|장비|설비|dfm|가공", "Advanced Manufacturing"),
    (r"industrial|산업용|하드웨어|hardware|기계|장치|module|모듈|전자부품|telecom|통신|display|광학", "Industrial Hardware"),
    (r"process", "Manufacturing Process Innovation"),
]
PROGRAM_FIELDS_SET = set(PROGRAM_FIELDS)


def normalize_field(raw: str) -> str:
    """자유 표기 → 공고 11개 분야 중 하나(불명확하면 Other Deeptech)."""
    if raw in PROGRAM_FIELDS_SET:
        return raw
    t = (raw or "").lower()
    for pat, canon in _FIELD_MAP:
        if _re.search(pat, t):
            return canon
    return "Other Deeptech"


def cache_key(biz_no: str, desc: str) -> str:
    """캐시 키 = 사업자번호 + 소개문 해시 + 모델. 프롬프트 버전은 키가 아니라 **항목 필드**로
    기록한다(v2/v3 선택적 재분류 혼재를 허용·추적). 소개문 해시가 서로 다른 회사를
    구분하므로 placeholder 사업자번호(해외법인 등)도 캐시에선 충돌하지 않는다."""
    h = hashlib.sha256((desc or "").encode("utf-8")).hexdigest()[:16]
    return f"{biz_no}|{h}|{MODEL}"


def load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def get_cached(rec: dict, cache: dict | None = None) -> dict | None:
    cache = cache if cache is not None else load_cache()
    return cache.get(cache_key(rec.get("biz_no", ""), rec.get("desc", "")))


def put(rec: dict, verdict: dict, cache: dict) -> None:
    verdict.setdefault("prompt_version", PROMPT_VERSION)
    cache[cache_key(rec.get("biz_no", ""), rec.get("desc", ""))] = verdict


def render_input(rec: dict) -> dict:
    """분류기에 넣을 최소 입력(업종·기술은 보조 신호로만)."""
    return {"biz_no": rec.get("biz_no", ""), "name": rec.get("name_ko", ""),
            "1줄_사업_소개": rec.get("desc", ""),
            "업종_보조신호": rec.get("industry", ""), "기술_보조신호": rec.get("tech", "")}
