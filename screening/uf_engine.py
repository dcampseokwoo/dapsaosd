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


# 스테이지 예외는 uf_stage 로 위임(§3). 하위호환 별칭 유지.
from screening.uf_stage import UnknownStageValue  # noqa: E402,F401


# ───────────────────────────────────────────── 스테이지 (§3)
def stage_bucket(value) -> str:
    """스테이지 값 → IN_SCOPE / UNKNOWN / EXCEPTION / OUT_OF_SCOPE. 미매칭은 예외(§3)."""
    from screening import uf_stage
    return uf_stage.stage_bucket(value)


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
    """소개문 기반 하드테크 분류(§1). LLM 판정 캐시(사업자번호+소개문해시+모델+프롬프트버전)에서 읽는다.

    캐시 미스면 unclear(low)로 보수적 처리 — 라벨 추측으로 통과/탈락시키지 않는다.
    """
    from screening import uf_classify
    c = uf_classify.get_cached({"biz_no": rec.get("biz_no", ""),
                                "desc": rec.get("desc", "")})
    if c:
        c = dict(c)
        c["matched_program_field"] = uf_classify.normalize_field(
            c.get("matched_program_field", ""))
        return c
    return {"verdict": "unclear", "matched_program_field": "None",
            "physical_product": False, "consumer_facing_end_product": False,
            "maturity_signal": "", "confidence": "low",
            "evidence": "(캐시 미스 — 미분류)"}


def hardtech_verdict(row: dict) -> str:
    """배제+분류를 합친 '이 회사가 하드테크인가'(스테이지 무관) — 분류 레이어 검증용."""
    if entity_verdict(row) == "not_a_startup":
        return "not_a_startup"
    return classify(row)["verdict"]
