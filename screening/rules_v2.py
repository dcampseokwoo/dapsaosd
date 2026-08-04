"""수정판 규칙 테이블 (v2) — v1 백테스트에서 드러난 4개 결함을 고친 버전.

가중치(Traction/TRL 40 · Team 30 · Market/양산 20 · Moat/고객 10)는
디캠프 내부 루브릭이므로 **건드리지 않는다**. 대신 레벨표와 집계 규칙만 고친다.

수정 1 — 스테이지 밴드별 레벨표 (BAND_TRACTION / BAND_TRL)
    v1 레벨표는 절대 기준이라 프리시드가 구조적으로 L2 상한에 갇혔다.
    ("Traction L5 = 지속 20% MoM + 유료 고객" — 매출 0인 밴드는 도달 불가)
    프롬프트 자신의 지시("얼마나 쌓았나가 아니라 얼마나 빨리 가나")대로
    밴드별로 '그 단계에서 가능한 최고 속도'를 L5 로 재정의한다.

수정 2 — `확인 필요`는 절대 레벨로 환산하지 않는다
    증거 등급 `문서 명시` 이상이 뒷받침하지 않으면 레벨을 매기지 않는다.
    v1 에서는 정보 부재가 L1(strict) 또는 L3(중간값 떠넘기기)로 흡수됐다.

수정 3 — 커버리지 규칙 (COVERAGE_MIN)
    레벨이 매겨진 축의 가중치 합이 기준 미만이면 Tier 를 내지 않고
    `판정 보류 — 정보 부족`. 탈락이 아니라 '설문·증빙 요청' 상태다.

수정 4 — 강등 규칙의 트랙별 분리 (DEMOTE_AXES)
    v1 은 어느 축이든 L1 이면 Tier 상한 C. 이 규칙이 HAX 와 충돌한다.
    HAX 는 고객 없는 랩 단계 하드테크에 투자하는 프로그램이므로
    고객 축 L1 을 강등 사유로 쓰면 프로그램 정의 자체와 모순된다.
"""
from __future__ import annotations

from screening.rules import (  # noqa: F401  (v1 과 공유)
    AXIS_LABELS, CRED_BROKEN, CRED_OK, GATE_COND, GATE_FAIL, GATE_HUMAN,
    GATE_PASS, PASS_TIERS, TIER_CUTOFFS, WEIGHTS, GateResult, Score,
    credibility_overall, gate_verdict, run_gates, _tier_of,
)

# 수정 3 — 레벨이 매겨진 축의 가중치 합이 이 값 미만이면 판정 보류
COVERAGE_MIN = 0.60
TIER_HOLD = "판정 보류 — 정보 부족"

# 수정 4 — 강등 규칙을 적용할 축 (트랙별)
#   500 : 제품이 없거나(Traction L1) 팀이 없으면(Team L1) 추천 불가
#   HAX : 기술이 개념뿐(TRL L1)이거나 팀이 없으면 추천 불가.
#         고객·양산 축 L1 은 프리시드 하드테크의 정상 상태이므로 강등 사유 아님
DEMOTE_AXES = {"500": ("traction", "team"), "hax": ("trl", "team")}

# 수정 1 — 스테이지 밴드별 Traction 레벨표 (500 트랙)
BAND_TRACTION = {
    "프리시드": {
        5: "출시 4주 내 외부 유료 전환 발생, 또는 재구매/리텐션 곡선 확인",
        4: "유료 고객 1곳 이상 (금액 무관) 또는 무료 사용자 급증",
        3: "외부 사용자 존재 (무료·파일럿 포함)",
        2: "제품 출시했으나 외부 사용 없음",
        1: "미출시",
    },
    "시드 초기": {
        5: "첫 유료 고객까지 6개월 이내 + 이후 유료 고객 증가",
        4: "유료 고객 1곳 이상 (금액 무관) 또는 무료 사용자 급증",
        3: "외부 사용자 존재 (무료·파일럿 포함)",
        2: "제품 출시했으나 외부 사용 없음",
        1: "미출시",
    },
    "시드 후기": {
        5: "지속 20%+ MoM 성장 + 조달 자본 대비 높은 효율",
        4: "유료 고객 + 명확한 우상향",
        3: "유료 고객 존재, 성장 정체 또는 미검증",
        2: "파일럿/LOI 만, 금전적 증거 없음",
        1: "외부 사용 없음",
    },
    "A 이후": {
        5: "지속 20%+ MoM 성장 + 조달 자본 대비 높은 효율",
        4: "유료 고객 + 명확한 우상향",
        3: "유료 고객 존재, 성장 정체 또는 미검증",
        2: "파일럿/LOI 만, 금전적 증거 없음",
        1: "외부 사용 없음",
    },
}

# 수정 1 — 스테이지 밴드별 TRL 레벨표 (HAX 트랙)
BAND_TRL = {
    "프리시드": {
        5: "랩 통합 프로토타입 동작 (TRL 4~5)",
        4: "핵심 원리 실증 + 정량 데이터 (TRL 3~4)",
        3: "핵심 원리 실증 (TRL 3)",
        2: "설계·시뮬레이션만 (TRL 2)",
        1: "개념만 (TRL 1)",
    },
    "시드 초기": {
        5: "관련 환경에서 검증된 통합 프로토타입 (TRL 5~6)",
        4: "실환경 실증 진행 중 (TRL 5)",
        3: "랩 프로토타입 (TRL 4)",
        2: "부분 모듈만 동작 (TRL 3)",
        1: "개념·설계 단계",
    },
    "시드 후기": {
        5: "운용 환경 실증 완료, 신뢰성 데이터 확보 (TRL 6~7)",
        4: "관련 환경 통합 프로토타입 (TRL 5~6)",
        3: "랩 프로토타입 (TRL 4)",
        2: "부분 모듈만 동작",
        1: "개념·설계 단계",
    },
    "A 이후": {
        5: "상용 배치·양산 검증 (TRL 8~9)",
        4: "운용 환경 실증 완료 (TRL 7)",
        3: "관련 환경 프로토타입 (TRL 5~6)",
        2: "랩 프로토타입",
        1: "개념·설계 단계",
    },
}


def band_table(track: str, band: str) -> dict[int, str] | None:
    """해당 트랙·밴드의 주축(Traction/TRL) 레벨표. 밴드 미확정이면 None."""
    return (BAND_TRACTION if track == "500" else BAND_TRL).get(band)


def aggregate(track: str, levels: dict[str, int | None],
              credibility: str = CRED_OK) -> Score:
    """v2 집계 — `확인 필요` 제외 + 커버리지 + 트랙별 강등."""
    w = WEIGHTS[track]
    lv = dict(levels)
    notes: list[str] = []

    main_axis = "traction" if track == "500" else "trl"
    if credibility == CRED_BROKEN and lv.get(main_axis) and lv[main_axis] > 2:
        lv[main_axis] = 2
        notes.append(f"신뢰성 붕괴 → {AXIS_LABELS[main_axis]} L2 상한 적용")

    used = {a: lv[a] for a in w if lv.get(a) is not None}
    unknown = [a for a in w if lv.get(a) is None]
    coverage = sum(w[a] for a in used)

    # 수정 3 — 커버리지 미달이면 Tier 를 내지 않는다 (탈락 아님)
    if coverage < COVERAGE_MIN:
        notes.append(
            f"레벨 확정 축 가중치 합 {coverage:.0%} < {COVERAGE_MIN:.0%} — "
            f"설문/증빙 요청 필요: {', '.join(AXIS_LABELS[a] for a in unknown)}")
        return Score("v2", None, TIER_HOLD, used, unknown, False, notes)

    weighted = sum(used[a] * w[a] for a in used) / coverage
    if unknown:
        notes.append("`확인 필요` 축 제외 후 재정규화: "
                     + ", ".join(AXIS_LABELS[a] for a in unknown))

    tier = _tier_of(weighted)
    demoted = False
    if any(used.get(a) == 1 for a in DEMOTE_AXES[track]) and tier in PASS_TIERS:
        tier, demoted = "C 보완 후 재도전", True
        notes.append("강등 규칙(트랙 핵심축 L1) 적용 → Tier 상한 C")
    return Score("v2", round(weighted, 3), tier, used, unknown, demoted, notes)
