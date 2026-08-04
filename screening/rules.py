"""d·camp 프리스크리닝 엔진 — 고정 규칙 테이블 (점수 계산부).

설계 원칙(프롬프트 원문): "점수를 매기지 마라. 사실을 분류하라. 점수는 규칙
테이블이 계산한다." 그 원칙을 코드로 강제한 모듈이다.

- 사실 → 레벨(L1~L5) 분류는 사람(또는 LLM)이 `dataset.py`에 기록한다.
- 레벨 → 가중평균 → Tier 변환은 오직 이 파일의 테이블이 수행한다.
  따라서 같은 레벨 입력이면 항상 같은 Tier가 나온다(결정성 보장 구간).

프롬프트가 정의하지 않아 여기서 보충한 값은 SPEC_GAPS 에 모두 적어 둔다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------- 축 가중치
# 프롬프트 명시값. 변경 금지(디캠프 내부 루브릭).
WEIGHTS = {
    "500": {"traction": 0.40, "team": 0.30, "market": 0.20, "moat": 0.10},
    "hax": {"trl": 0.40, "team": 0.30, "manufacturing": 0.20, "customer": 0.10},
}

AXIS_LABELS = {
    "traction": "Traction", "team": "Team", "market": "Market", "moat": "Moat",
    "trl": "TRL", "manufacturing": "양산 경로", "customer": "고객",
}

# ---------------------------------------------------------------- Tier 컷오프
# ⚠ 프롬프트는 "가중 레벨 평균 → 잠정 등급"이라고만 하고 컷오프를 주지 않는다.
# 아래는 이 백테스트에서 사용한 보충값 — 엔진의 판정은 이 숫자에 직접 의존한다.
TIER_CUTOFFS = [
    (4.00, "A 추천"),
    (3.25, "B 확인 후 추천"),
    (2.50, "C 보완 후 재도전"),
    (0.00, "D 부적합"),
]
PASS_TIERS = ("A 추천", "B 확인 후 추천")   # '추천 대상'으로 간주하는 Tier

SPEC_GAPS = [
    "Tier 컷오프(가중평균 → A/B/C/D) 미정의 — 4.00/3.25/2.50 으로 보충 적용",
    "`확인 필요` 축의 점수 처리 미정의 — 운영원칙1(감점 금지)과 레벨표(증거 없으면 하위 레벨)가 충돌. strict/neutral 두 모드로 분리 계산",
    "신뢰성 `붕괴` 시 Traction 상한 L2 규정은 있으나 HAX 축(TRL 등)에 대한 상한 규정 없음",
    "Fit(높음/중간/낮음)은 정성 판단만 규정 — 규칙 테이블 없음(결정성 미보장 구간)",
    "앵커 9개사 중 3개(SECA/Wesley/Provally)만 제시 — 나머지 미제공 시 다수 축이 `판정 불안정`",
]

# ---------------------------------------------------------------- 하드 게이트
# 반환: (verdict, 근거) — verdict ∈ 통과 / 조건부 / 탈락 / 사람 검토
GATE_PASS, GATE_COND, GATE_FAIL, GATE_HUMAN = "통과", "조건부", "탈락", "사람 검토"

# HAX 제외 섹터 (Step 0 웹 확인: HAX = 하드웨어/기후/산업자동화/헬스 하드웨어)
HAX_EXCLUDED = ("pure_sw", "fintech", "crypto", "security", "ecommerce")
BIO_SECTORS = ("bio", "therapeutics", "synbio")


@dataclass
class GateResult:
    name: str
    verdict: str
    reason: str


def run_gates(c: "object") -> list[GateResult]:
    """트랙별 하드 게이트 판정. c 는 dataset.Company."""
    g: list[GateResult] = []
    if c.track == "500":
        g.append(GateResult(
            "테크 기업 + 동작하는 프로토타입",
            GATE_PASS if c.has_working_product else GATE_FAIL,
            c.product_note))
        g.append(GateResult(
            "풀타임 / 리로케이션 의사",
            GATE_PASS if c.fulltime_confirmed and c.relocation_confirmed else GATE_COND,
            c.commitment_note))
        g.append(GateResult(
            "스테이지 (A 이후면 에스컬레이션)",
            GATE_HUMAN if c.stage_band == "A 이후" else GATE_PASS,
            f"스테이지 밴드: {c.stage_band}"))
    elif c.track == "hax":
        excluded = c.sector_key in HAX_EXCLUDED
        g.append(GateResult(
            "HAX 제외 섹터 여부",
            GATE_FAIL if excluded else GATE_PASS,
            c.sector_note))
        # 라이브 조건(Step 0): 첫 투자 $250K(현금 $150K + 인킨드 $100K),
        # 캡 없는 post-money SAFE — 기존 프라이스드 라운드와 충돌 가능
        if c.stage_band == "A 이후":
            g.append(GateResult("기존 프라이스드 라운드 / HAX 조건 충돌",
                                GATE_FAIL, "시리즈A 이후 — 프리시드 SAFE 조건과 충돌"))
        elif c.priced_round:
            g.append(GateResult("기존 프라이스드 라운드 / HAX 조건 충돌",
                                GATE_COND, "프라이스드 라운드 존재 — 조건 협의 필요"))
        else:
            g.append(GateResult("기존 프라이스드 라운드 / HAX 조건 충돌",
                                GATE_PASS, "프리시드/시드 SAFE 수용 가능"))
        g.append(GateResult(
            "HAX 지분(약 10%) 캡테이블 수용 가능",
            GATE_PASS if c.cap_table_ok else GATE_COND, c.cap_table_note))
    g.append(GateResult(
        "C레벨 영어 (영어 전용 프로그램)",
        GATE_PASS if c.english_ok else GATE_COND, c.english_note))
    return g


def gate_verdict(gates: list[GateResult]) -> str:
    """게이트 종합 — 하나라도 탈락이면 탈락, 사람 검토 > 조건부 > 통과."""
    v = [g.verdict for g in gates]
    for level in (GATE_FAIL, GATE_HUMAN, GATE_COND):
        if level in v:
            return level
    return GATE_PASS


# ---------------------------------------------------------------- 신뢰성 스캔
CRED_OK, CRED_WARN, CRED_BROKEN = "정상", "경계", "붕괴"
_CRED_ORDER = {CRED_OK: 0, CRED_WARN: 1, CRED_BROKEN: 2}


def credibility_overall(items: dict[str, str]) -> str:
    """전체 신뢰성 = 개별 항목 중 최악값."""
    if not items:
        return CRED_OK
    return max(items.values(), key=lambda v: _CRED_ORDER[v])


# ---------------------------------------------------------------- 집계
@dataclass
class Score:
    mode: str
    weighted: float | None
    tier: str
    used_axes: dict[str, int]
    unknown_axes: list[str]
    demoted: bool = False
    notes: list[str] = field(default_factory=list)


def _tier_of(weighted: float) -> str:
    for cut, tier in TIER_CUTOFFS:
        if weighted >= cut:
            return tier
    return TIER_CUTOFFS[-1][1]


def aggregate(track: str, levels: dict[str, int | None], mode: str,
              credibility: str = CRED_OK) -> Score:
    """레벨 → Tier. mode 는 두 가지 해석 중 하나를 고른다.

    strict  : `확인 필요` 축을 L1 으로 본다 (레벨표를 문자 그대로 적용).
    neutral : `확인 필요` 축을 계산에서 제외하고 남은 가중치를 재정규화한다
              (운영원칙1 "불명 = 0점이 아니다" 를 문자 그대로 적용).
    """
    w = WEIGHTS[track]
    lv = dict(levels)
    notes: list[str] = []

    # 신뢰성 붕괴 → Traction 상한 L2 (프롬프트 명시 규칙; 500 트랙에만 정의됨)
    if credibility == CRED_BROKEN and "traction" in lv and (lv["traction"] or 0) > 2:
        lv["traction"] = 2
        notes.append("신뢰성 붕괴 → Traction L2 로 상한 적용")

    unknown = [a for a in w if lv.get(a) is None]

    if mode == "strict":
        used = {a: (lv.get(a) or 1) for a in w}
        weighted = sum(used[a] * w[a] for a in w)
    elif mode == "neutral":
        used = {a: lv[a] for a in w if lv.get(a) is not None}
        wsum = sum(w[a] for a in used)
        if wsum == 0:
            return Score(mode, None, "판정 불가", {}, unknown, False,
                         notes + ["모든 축이 `확인 필요` — 점수 산출 불가"])
        weighted = sum(used[a] * w[a] for a in used) / wsum
        if unknown:
            notes.append(f"`확인 필요` 축 제외 후 재정규화: {', '.join(unknown)}")
    else:
        raise ValueError(mode)

    tier = _tier_of(weighted)
    # 강등 규칙: 어느 축이든 L1 이면 최종 Tier 는 C 를 넘을 수 없다
    demoted = False
    if any(v == 1 for v in used.values()) and tier in ("A 추천", "B 확인 후 추천"):
        tier, demoted = "C 보완 후 재도전", True
        notes.append("강등 규칙 적용: L1 축 존재 → Tier 상한 C")
    return Score(mode, round(weighted, 3), tier, used, unknown, demoted, notes)
