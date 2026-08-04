"""v3 — 불확실성 전파 구조 (확정 판정 / 사람 검토 분리).

왜 v3 가 필요한가
-----------------
v2 는 `확인 필요` 축을 제외하고 남은 축으로 **점추정 하나**를 낸다. 그래서
근거가 60% 뿐인 기업도 "B 확인 후 추천" 같은 단정을 받는다. 실제로 이 구조가
SaaSMetrics(500 실제 탈락)를 B 로 통과시켰다 — Market 축을 모르는 상태였는데,
모른다는 사실이 판정에 반영되지 않았기 때문이다.

v3 의 변경은 하나뿐이다: **점추정을 구간추정으로 바꾼다.**

    확인 필요 축      → 가능 범위 L1~L5 로 전파
    경계 판정 축      → 기록된 대안 레벨까지 범위로 전파 (인접 레벨만)
    확정 축          → 그 값 고정

    weighted_min = Σ(하한 × 가중치)      weighted_max = Σ(상한 × 가중치)

    구간 전체가 추천선 이상  → `확정 추천`
    구간 전체가 추천선 미만  → `확정 비추천`
    구간이 추천선을 걸침     → `사람 검토` (엔진이 결론을 내지 않는다)

이 구조는 **라벨을 보지 않는다.** 합불 데이터에 맞춰 튜닝한 것이 아니라,
이미 dataset 에 기록해 둔 불확실성을 판정까지 끌고 온 것뿐이다. 따라서
표본 과적합이 아니다.

대가: 결론을 내는 비율이 떨어진다. 그 비율은 규칙의 한계가 아니라
**제출 자료의 한계**이며, experiment.py 가 둘을 분리해 측정한다.
"""
from __future__ import annotations

from dataclasses import dataclass

from screening.rules import AXIS_LABELS, GATE_FAIL, GATE_HUMAN, WEIGHTS
from screening.rules_v2 import FIT_LOW

# 추천선 — v2 의 B 컷오프와 동일 값을 쓴다 (판정 기준을 바꾸지 않기 위해)
RECOMMEND_LINE = 3.25

ZONE_YES, ZONE_NO, ZONE_HUMAN = "확정 추천", "확정 비추천", "사람 검토"

LEVEL_MIN, LEVEL_MAX = 1, 5


@dataclass
class Interval:
    zone: str
    lo: float
    hi: float
    width: float
    unknown_axes: list[str]
    unstable_axes: list[str]
    # 구간 폭 중 `확인 필요` 축이 만든 비중 (자료 부재 탓 vs 판정 경계 탓)
    width_from_unknown: float
    notes: list[str]


def _ranges(track: str, levels: dict[str, int | None],
            unstable: dict[str, int]) -> tuple[dict, list[str], list[str]]:
    """축별 (하한, 상한) 범위. 인접 레벨 대안만 경계로 인정한다."""
    rng, unknown, unst = {}, [], []
    for axis in WEIGHTS[track]:
        lv = levels.get(axis)
        if lv is None:
            rng[axis] = (LEVEL_MIN, LEVEL_MAX)
            unknown.append(axis)
            continue
        alt = unstable.get(axis)
        if alt is not None and abs(alt - lv) == 1:
            rng[axis] = (min(lv, alt), max(lv, alt))
            unst.append(axis)
        else:
            rng[axis] = (lv, lv)
    return rng, unknown, unst


def decide(track: str, levels: dict[str, int | None],
           unstable: dict[str, int] | None = None,
           gate: str = "통과") -> Interval:
    """구간추정 → 3구역 판정."""
    unstable = unstable or {}
    w = WEIGHTS[track]
    rng, unknown, unst = _ranges(track, levels, unstable)

    lo = sum(rng[a][0] * w[a] for a in w)
    hi = sum(rng[a][1] * w[a] for a in w)
    width = hi - lo
    # 폭 분해: `확인 필요` 축이 기여한 폭
    w_unknown = sum((LEVEL_MAX - LEVEL_MIN) * w[a] for a in unknown)

    notes = []
    if gate == GATE_FAIL:
        zone = ZONE_NO
        notes.append("게이트 탈락 — 구간과 무관하게 비추천")
    elif gate == GATE_HUMAN:
        zone = ZONE_HUMAN
        notes.append("게이트 사람 검토 — 에스컬레이션")
    elif lo >= RECOMMEND_LINE:
        zone = ZONE_YES
        notes.append(f"최악 가정(하한 {lo:.2f})에서도 추천선 {RECOMMEND_LINE} 이상")
    elif hi < RECOMMEND_LINE:
        zone = ZONE_NO
        notes.append(f"최선 가정(상한 {hi:.2f})으로도 추천선에 미달")
    else:
        zone = ZONE_HUMAN
        notes.append(f"구간 [{lo:.2f}, {hi:.2f}] 이 추천선 {RECOMMEND_LINE} 을 걸침 "
                     f"— 엔진이 단정하지 않는다")
    if unknown:
        share = f" (구간 폭의 {w_unknown / width:.0%})" if width else ""
        notes.append("`확인 필요` 축: "
                     + ", ".join(AXIS_LABELS[a] for a in unknown) + share)
    if unst:
        notes.append("경계 판정 축: " + ", ".join(AXIS_LABELS[a] for a in unst))
    return Interval(zone, round(lo, 3), round(hi, 3), round(width, 3),
                    unknown, unst, round(w_unknown, 3), notes)


def action_of(iv: Interval, fit: str) -> str:
    """구역 × Fit → 조치."""
    if iv.zone == ZONE_YES:
        return {"높음": "추천 진행", "중간": "조건부 추천 — 확인사항 해소 후"}.get(
            fit, "타 프로그램 추천 (Quality 는 충분)")
    if iv.zone == ZONE_NO:
        return "비추천 — 사유 통지 + 자가진단 제공"
    # 사람 검토 — Fit 이 낮으면 자료를 더 받아도 결론이 안 바뀐다
    if fit == FIT_LOW:
        return "타 프로그램 안내 (Fit 낮음 — 추가 자료 불필요)"
    if iv.unknown_axes:
        return ("설문·증빙 요청 → 재판정 (미확보 축: "
                + ", ".join(AXIS_LABELS[a] for a in iv.unknown_axes) + ")")
    return "담당자 검토 — 자료는 충분하나 판정이 경계에 있음"
