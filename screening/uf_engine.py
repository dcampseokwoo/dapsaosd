"""US FORGED 엔진 — 레이어 인터페이스 (facade).

골든셋 하네스가 호출하는 안정적 인터페이스. 지금은 **baseline** 구현 = 현재의
CB 업종 라벨 로직에 위임한다(감사에서 무너진 그 로직). §1~§4 에서 각 함수 본문을
실제 구현(LLM 분류·스테이지 재작성·배제 강화)으로 교체하되, 하네스와 시그니처는
그대로 둔다 → 회귀를 감지한다.

레이어(파이프라인 순서): 배제(§4) → 스테이지(§3) → 분류(§1).
분류·배제는 스테이지와 무관(stage-independent), 스테이지는 값→버킷 매핑만.
"""
from __future__ import annotations

# 캐시 키 구성요소(§1 LLM 분류에서 사용) — baseline 은 라벨 로직이라 미사용
MODEL = "baseline-label-logic"
PROMPT_VERSION = "v0"
ENGINE_VERSION = "baseline-0"

# 공고 11개 모집 분야
PROGRAM_FIELDS = [
    "Robotics/Automation", "Advanced Manufacturing", "Energy/Climate Tech",
    "Industrial Hardware", "Semiconductor/Advanced Materials", "Sensor/Edge Device",
    "Physical AI", "Healthtech Device", "Manufacturing Process Innovation",
    "Aerospace", "Quantum", "Other Deeptech", "None",
]

VERDICTS = ("hardtech", "software_only", "consumer", "not_a_startup", "unclear")


class UnknownStageValue(Exception):
    """스테이지 값이 매핑에 없음 — 조용히 탈락시키지 말고 예외를 던진다(§3)."""


# ───────────────────────────────────────────── 스테이지 (§3) — baseline
def stage_bucket(value) -> str:
    """스테이지 값 → IN_SCOPE / UNKNOWN / EXCEPTION / OUT_OF_SCOPE. 미매칭은 예외.

    BASELINE: 현재 us_forged.stage_status(OK/UNKNOWN/LATER)를 매핑. EXCEPTION·RAISE
    없음 → 골든셋 stage_rules 에서 Pre-seed/Pre-A/Pre-B/미매칭이 깨진다(그게 baseline).
    """
    from screening import us_forged as legacy
    st = legacy.stage_status("" if value is None else str(value))
    return {"OK": "IN_SCOPE", "UNKNOWN": "UNKNOWN", "LATER": "OUT_OF_SCOPE"}[st]


# ───────────────────────────────────────────── 배제 (§4) — baseline
def entity_verdict(row: dict) -> str:
    """법인격/해외법인 배제 → 'ok' | 'not_a_startup'.

    BASELINE: 현재 us_forged._NON_STARTUP(사명 정규식)만. 사업자번호 형식(OC*·외국법인_*·
    해외법인)은 보지 않음 → Zhongxing/Lihua 등 해외법인이 안 잡힌다(그게 baseline).
    """
    from screening import us_forged as legacy
    name = (row.get("name_ko", "") or "") + " " + (row.get("name_en", "") or "")
    return "not_a_startup" if legacy._NON_STARTUP.search(name) else "ok"


# ───────────────────────────────────────────── 분류 (§1) — baseline
def classify(rec: dict) -> dict:
    """소개문 기반 하드테크 분류. 반환 스키마는 §1 그대로.

    BASELINE: 현재 CB 업종 가드 로직(us_forged._cb_hardtech)에 위임 → 라벨로 판정.
    한글 레거시 라벨·다중 라벨을 오탈락시키고, SW/소비재를 라벨만 보고 통과시킨다.
    §1 에서 LLM 소개문 분류로 교체 예정.
    """
    from screening import us_forged as legacy
    # 스냅샷 행 키(industry) → legacy 가 기대하는 키(sector)
    ad = {"sector": rec.get("industry", rec.get("sector", "")),
          "tech": rec.get("tech", ""), "desc": rec.get("desc", ""),
          "svc": rec.get("svc", ""), "name_ko": rec.get("name_ko", ""),
          "name_en": rec.get("name_en", "")}
    fine_ok = legacy.fine_confirmed(ad)
    hard, basis = legacy._cb_hardtech(ad["sector"], fine_ok)
    if hard:
        return {"verdict": "hardtech", "matched_program_field": "Other Deeptech",
                "physical_product": True, "confidence": "low",
                "evidence": f"(baseline: CB 라벨 {basis})"}
    return {"verdict": "software_only", "matched_program_field": "None",
            "physical_product": False, "confidence": "low",
            "evidence": f"(baseline: CB 라벨 {basis} — 하드테크 아님으로 처리)"}


def hardtech_verdict(row: dict) -> str:
    """배제+분류를 합친 '이 회사가 하드테크인가'(스테이지 무관) — 분류 레이어 검증용."""
    if entity_verdict(row) == "not_a_startup":
        return "not_a_startup"
    return classify(row)["verdict"]
