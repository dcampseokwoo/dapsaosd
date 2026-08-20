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

MODEL = "claude-agent"        # 분류 수행 모델(캐시 무효화 키). 런타임 API 붙이면 실제 id 로.
PROMPT_VERSION = "v1"

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

■ 경계형 처리 (감사에서 판단 유보됐던 유형 — 여기서 일관성이 드러난다)
1) 파운드리·수탁제조(남의 설계를 위탁생산, 자체 제품/IP 언급 없음)
   → 자체 기술 차별성이 소개에 없으면 unclear(수탁제조 의심), confidence 낮게. 자체 제품·
     독자 공정이 명시되면 hardtech.
2) 소재 상사·무역·유통(소재를 다루지만 직접 제조가 아니라 유통) → physical_product=false,
   verdict unclear(직접 제조 아님, 유통).
3) 연구용역·엔지니어링 컨설팅(하드웨어를 다루지만 자체 제품 없음, 용역 제공) → unclear.
4) 하드웨어 + SaaS 결합(센서·디바이스를 직접 만들어 팔고 데이터 구독을 붙임) → hardtech.
5) 기성 부품 제조 중소기업(범용 부품을 오래 만들어온 제조업체 느낌) → 물리적 제조는
   맞으므로 hardtech 로 두되, evidence 에 '범용/기성 부품 제조 뉘앙스'를 반드시 적어라
   (스타트업 여부는 다른 단계에서 본다).

■ physical_product (boolean)
물리적 제품을 **직접 설계·제조**하면 true. 유통·중개·용역·순수 SW 면 false.

■ 출력: 아래 JSON 스키마 정확히. evidence 는 판정 근거가 된 **소개문 구절을 원문 그대로
인용**(요약·창작 금지). matched_program_field 는 11개 중 하나 또는 Other Deeptech/None.

{
  "biz_no": "<입력 그대로>",
  "verdict": "hardtech|software_only|consumer|not_a_startup|unclear",
  "matched_program_field": "<위 목록 중 하나>",
  "physical_product": true|false,
  "evidence": "<소개문 원문 인용>",
  "confidence": "high|medium|low"
}
"""


def cache_key(biz_no: str, desc: str) -> str:
    h = hashlib.sha256((desc or "").encode("utf-8")).hexdigest()[:16]
    return f"{biz_no}|{h}|{MODEL}|{PROMPT_VERSION}"


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
    cache[cache_key(rec.get("biz_no", ""), rec.get("desc", ""))] = verdict


def render_input(rec: dict) -> dict:
    """분류기에 넣을 최소 입력(업종·기술은 보조 신호로만)."""
    return {"biz_no": rec.get("biz_no", ""), "name": rec.get("name_ko", ""),
            "1줄_사업_소개": rec.get("desc", ""),
            "업종_보조신호": rec.get("industry", ""), "기술_보조신호": rec.get("tech", "")}
