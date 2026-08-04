"""일치율 측정 — 독립 분류(Fable) 대 기존 분류(Claude) — 작업 1-3 / 2-3.

  python -m screening.agreement            # 지표 출력
  python -m screening.agreement --report   # screening/AGREEMENT.md 생성

측정하는 것
  1) 완전/인접/None 일치율, Cohen's κ (순수 파이썬 — 외부 의존성 없음)
  2) 축별 일치율 — 주축(Traction/TRL), Team, Market/양산, Moat/고객
  3) 불일치가 v2 Tier·v3 구역을 바꾸는가
  4) CONFIDENCE="low" 표시가 실제 불일치를 예측하는가
  5) 레벨 정의 개선(작업 2-2) 전후의 일치율 변화
  6) 분류자를 바꿨을 때 실험 1·2 의 결론이 바뀌는가

블라인드 절차: LEVELS_FABLE 은 dataset.py 를 읽은 적 없는 격리 세션이
output/screening/blind_input.json 만 보고 생성했다. 이 모듈이 처음으로
두 분류를 나란히 놓는다.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from screening import backtest, dataset, rules, rules_v2, rules_v3
from screening.levels_fable import (ALT, CONFIDENCE, LEVELS_FABLE,
                                    RECLASSIFIED, unstable_of)

BASE = Path(__file__).resolve().parent.parent

# 축 → 비교 그룹 (500 과 HAX 의 대응 축을 같은 그룹으로)
AXIS_ROLE = {
    "traction": "Traction/TRL", "trl": "Traction/TRL",
    "team": "Team",
    "market": "Market/양산", "manufacturing": "Market/양산",
    "moat": "Moat/고객", "customer": "Moat/고객",
}


# ---------------------------------------------------------------- 축 페어
def merged_fable(with_reclassified: bool = False) -> dict:
    """Fable 분류. with_reclassified=True 면 작업 2-3 재분류를 덮어쓴다."""
    out = {k: dict(v) for k, v in LEVELS_FABLE.items()}
    if with_reclassified:
        for k, axes in RECLASSIFIED.items():
            out.setdefault(k, {}).update(axes)
    return out


def axis_pairs(fable: dict | None = None) -> list[dict]:
    """기업×축 단위의 (Claude 레벨, Fable 레벨, 두 근거)."""
    fable = fable or LEVELS_FABLE
    rows = []
    for key, cl_axes in dataset.LEVELS_V2.items():
        c = dataset.by_key(key)
        fb_axes = fable.get(key, {})
        for axis in rules.WEIGHTS[c.track]:
            cl_lv, cl_why = cl_axes[axis]
            fb_lv, fb_why = fb_axes.get(axis, (None, "누락"))
            rows.append({
                "key": key, "name": c.name, "axis": axis,
                "role": AXIS_ROLE[axis],
                "claude": cl_lv, "fable": fb_lv,
                "claude_why": cl_why, "fable_why": fb_why,
                "confidence": CONFIDENCE.get(key, {}).get(axis, "high"),
            })
    return rows


# ---------------------------------------------------------------- 일치율
def _exact(a, b) -> bool:
    return a == b


def _adjacent(a, b) -> bool:
    """±1 레벨까지 일치로 본다. None 은 None 하고만 일치한다."""
    if a is None or b is None:
        return a is b
    return abs(a - b) <= 1


def _none_agree(a, b) -> bool:
    """`확인 필요` 판단 자체의 일치 — 증거 등급 규칙(§4)의 재현성."""
    return (a is None) == (b is None)


def rates(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "n_axes": n,
        "exact": round(sum(_exact(r["claude"], r["fable"]) for r in rows) / n, 3),
        "adjacent": round(sum(_adjacent(r["claude"], r["fable"]) for r in rows) / n, 3),
        "none_agree": round(sum(_none_agree(r["claude"], r["fable"]) for r in rows) / n, 3),
        "kappa": kappa([(r["claude"], r["fable"]) for r in rows]),
    }


def kappa(pairs: list[tuple]) -> float:
    """Cohen's κ — None 도 하나의 범주로 취급. 순수 파이썬 구현."""
    n = len(pairs)
    if n == 0:
        return 0.0
    cats = sorted({x for p in pairs for x in p}, key=lambda v: (v is None, v))
    po = sum(1 for a, b in pairs if a == b) / n
    pe = 0.0
    for c in cats:
        pa = sum(1 for a, _ in pairs if a == c) / n
        pb = sum(1 for _, b in pairs if b == c) / n
        pe += pa * pb
    if pe == 1.0:              # 두 평가자가 전 축을 단일 범주로 분류한 퇴화 사례
        return 1.0 if po == 1.0 else 0.0
    return round((po - pe) / (1 - pe), 3)


def by_role(rows: list[dict]) -> dict:
    out = {}
    for role in ("Traction/TRL", "Team", "Market/양산", "Moat/고객"):
        sub = [r for r in rows if r["role"] == role]
        out[role] = {
            "n": len(sub),
            "exact": round(sum(_exact(r["claude"], r["fable"]) for r in sub) / len(sub), 3),
            "adjacent": round(sum(_adjacent(r["claude"], r["fable"]) for r in sub) / len(sub), 3),
        }
    return out


def disagreements(rows: list[dict], adjacent_only: bool = False) -> list[dict]:
    """불일치 축 — adjacent_only=True 면 ±1 을 넘는 불일치만."""
    test = _adjacent if adjacent_only else _exact
    return [r for r in rows if not test(r["claude"], r["fable"])]


# ---------------------------------------------------------------- Tier 영향
def _fable_levels_only(fable: dict, key: str) -> dict:
    return {a: v[0] for a, v in fable[key].items()}


def tier_impact(fable: dict | None = None) -> list[dict]:
    """두 분류를 각각 v2 집계·v3 판정에 넣어 Tier·구역이 달라지는 기업."""
    fable = fable or LEVELS_FABLE
    out = []
    for key in dataset.LEVELS_V2:
        c = dataset.by_key(key)
        cred = rules.credibility_overall(c.credibility)
        gate = rules.gate_verdict(rules.run_gates(c))
        cl_lv = dataset.levels_v2_of(c)
        fb_lv = _fable_levels_only(fable, key)

        t_cl = rules_v2.aggregate(c.track, cl_lv, cred).tier
        t_fb = rules_v2.aggregate(c.track, fb_lv, cred).tier
        z_cl = rules_v3.decide(c.track, cl_lv, c.unstable, gate).zone
        z_fb = rules_v3.decide(c.track, fb_lv, unstable_of(key), gate).zone

        diff_axes = [a for a in rules.WEIGHTS[c.track]
                     if cl_lv.get(a) != fb_lv.get(a)]
        if t_cl != t_fb or z_cl != z_fb:
            out.append({"key": key, "name": c.name,
                        "tier_claude": t_cl, "tier_fable": t_fb,
                        "zone_claude": z_cl, "zone_fable": z_fb,
                        "diff_axes": diff_axes})
    return out


# ---------------------------------------------------------------- CONFIDENCE 검증
def confidence_overlap(rows: list[dict]) -> dict:
    """"low" 표시가 실제 불일치(완전 불일치 기준)와 얼마나 겹치는가."""
    low = [r for r in rows if r["confidence"] == "low"]
    dis = disagreements(rows)
    low_and_dis = [r for r in low if not _exact(r["claude"], r["fable"])]
    return {
        "n_low": len(low), "n_disagree": len(dis),
        "n_overlap": len(low_and_dis),
        # low 표시 중 실제로 불일치한 비율 (정밀도)
        "precision": round(len(low_and_dis) / len(low), 3) if low else None,
        # 불일치 중 low 로 예고된 비율 (재현율)
        "recall": round(len(low_and_dis) / len(dis), 3) if dis else None,
    }


# ---------------------------------------------------------------- 개선 효과
def improvement_effect() -> dict | None:
    """작업 2-3 — 재분류 전후의 일치율. RECLASSIFIED 가 비어 있으면 None."""
    if not RECLASSIFIED:
        return None
    before_rows = axis_pairs(merged_fable(False))
    after_rows = axis_pairs(merged_fable(True))
    changed = {(k, a) for k, axes in RECLASSIFIED.items() for a in axes}
    b_sub = [r for r in before_rows if (r["key"], r["axis"]) in changed]
    a_sub = [r for r in after_rows if (r["key"], r["axis"]) in changed]
    return {
        "n_reclassified": len(changed),
        "overall_before": rates(before_rows), "overall_after": rates(after_rows),
        "subset_before": {
            "exact": round(sum(_exact(r["claude"], r["fable"]) for r in b_sub) / len(b_sub), 3),
            "adjacent": round(sum(_adjacent(r["claude"], r["fable"]) for r in b_sub) / len(b_sub), 3),
        },
        "subset_after": {
            "exact": round(sum(_exact(r["claude"], r["fable"]) for r in a_sub) / len(a_sub), 3),
            "adjacent": round(sum(_adjacent(r["claude"], r["fable"]) for r in a_sub) / len(a_sub), 3),
        },
    }


# ---------------------------------------------------------------- 분류자 교체 실험
def run_with_fable(with_reclassified: bool = False) -> list[dict]:
    """dataset 의 분류를 Fable 분류로 잠시 바꿔 backtest.run() 실행.

    사실(facts)·게이트·Fit·신뢰성은 그대로 두고 **레벨 분류만** 바꾼다 —
    '분류자가 바뀌면 결론이 바뀌는가'를 그 구간만 분리해 측정하기 위해서다.
    """
    fable = merged_fable(with_reclassified)
    saved_levels = dataset.LEVELS_V2
    saved_unstable = {c.key: c.unstable for c in dataset.COMPANIES}
    dataset.LEVELS_V2 = fable
    for c in dataset.COMPANIES:
        c.unstable = unstable_of(c.key)
    try:
        return backtest.run()
    finally:
        dataset.LEVELS_V2 = saved_levels
        for c in dataset.COMPANIES:
            c.unstable = saved_unstable[c.key]


def classifier_swap(with_reclassified: bool = False) -> dict:
    """실험 1(성적표)·실험 2(확정 판정)를 두 분류로 각각 계산."""
    from screening import experiment
    r_cl = backtest.run()
    r_fb = run_with_fable(with_reclassified)
    out = {
        "claude": {"exp1": experiment.exp1_scoreboard(r_cl),
                   "exp2": experiment.exp2_confident(r_cl)},
        "fable": {"exp1": experiment.exp1_scoreboard(r_fb),
                  "exp2": experiment.exp2_confident(r_fb)},
    }
    # SaaSMetrics — 어느 분류에서도 `확정 추천`이 나오면 안 된다
    for tag, rs in (("claude", r_cl), ("fable", r_fb)):
        r = next(x for x in rs if x["company"].key == "saasmetrics")
        out[tag]["saasmetrics"] = {"v2_tier": r["scores"]["v2"].tier,
                                   "v3_zone": r["v3"].zone}
    return out


# ---------------------------------------------------------------- 리포트
def _lv(v) -> str:
    return f"L{v}" if v is not None else "`확인 필요`"


def render() -> str:
    rows = axis_pairs()
    r = rates(rows)
    roles = by_role(rows)
    dis = disagreements(rows)
    dis_far = disagreements(rows, adjacent_only=True)
    impact = tier_impact()
    conf = confidence_overlap(rows)
    imp = improvement_effect()
    swap_raw = classifier_swap(with_reclassified=False)
    swap = classifier_swap(with_reclassified=bool(RECLASSIFIED))

    L = ["# 사실→레벨 분류의 재현성 측정 — 블라인드 재분류 결과", ""]
    L.append("엔진의 미검증 구간(사실 → L1~L5 분류)을 독립 평가자로 측정했다. "
             "레벨→Tier 구간은 코드가 강제하므로(테스트 54건), 이 측정이 "
             "\"같은 사실이면 같은 점수\" 주장의 남은 절반을 처음으로 검증한다.")
    L.append("")
    L.append("## 0. 블라인드 절차 확인")
    L.append("")
    L.append("- 독립 분류(LEVELS_FABLE)는 **dataset.py 를 읽은 적 없는 격리 세션**이 "
             "수행했다. 입력은 `output/screening/blind_input.json`(사실·증거 등급만, "
             "`blind_fixture.py` 가 화이트리스트로 생성) + §3 레벨표·§4 증거 등급 규칙뿐이다.")
    L.append("- 격리 세션에는 ENGINE_V2.md 원문도 주지 않았다 — §6·§12 에 기존 분류의 "
             "일부(Still Bright 고객 L1, SaaSMetrics Market `확인 필요`)가 적혀 있어, "
             "§3·§4 만 발췌해 전달했다.")
    L.append("- **작업 1-2 가 끝날 때까지 격리 세션은 Claude 의 분류"
             "(dataset.LEVELS_V2)·정답 라벨(ground_truth)·비고(note)를 보지 않았다.** "
             "오케스트레이션한 메인 세션은 dataset.py 를 읽었으므로 직접 분류하지 않았다.")
    L.append("- 한계: `facts` 문장 일부에 합격/탈락 사실이 포함된다(예: \"500 플래그십 "
             "참가 확정\", \"탈락을 직접 공개\"). 격리 세션에는 결과 사실과 `[후행]` "
             "사실을 레벨 근거로 쓰지 말라고 지시했고, 근거 문장에서 사용 여부를 "
             "확인했다 — 그래도 완전한 결과 차단은 아니며, 이는 데이터셋 구조의 한계다.")
    L.append("")

    L.append("## 1. 일치율")
    L.append("")
    L.append(f"19개사 × 4축 = **{r['n_axes']}개 축** (바이오 라우팅 1개사 제외)")
    L.append("")
    L.append("| 지표 | 값 |")
    L.append("|---|---|")
    L.append(f"| 완전 일치율 (None 포함) | **{r['exact']:.0%}** |")
    L.append(f"| 인접 일치율 (±1) | **{r['adjacent']:.0%}** |")
    L.append(f"| None 일치율 (`확인 필요` 판단의 재현성) | **{r['none_agree']:.0%}** |")
    L.append(f"| Cohen's κ | **{r['kappa']}** |")
    L.append("")
    L.append("### 축별")
    L.append("")
    L.append("| 축 | n | 완전 일치 | 인접 일치 |")
    L.append("|---|---|---|---|")
    for role, d in roles.items():
        L.append(f"| {role} | {d['n']} | {d['exact']:.0%} | {d['adjacent']:.0%} |")
    L.append("")

    L.append("## 2. 불일치가 Tier·구역을 바꾸는 기업")
    L.append("")
    if impact:
        L.append("| 기업 | v2 Tier (Claude → Fable) | v3 구역 (Claude → Fable) | 갈린 축 |")
        L.append("|---|---|---|---|")
        for d in impact:
            axes = ", ".join(rules.AXIS_LABELS[a] for a in d["diff_axes"])
            L.append(f"| {d['name']} | {d['tier_claude']} → {d['tier_fable']} | "
                     f"{d['zone_claude']} → {d['zone_fable']} | {axes} |")
    else:
        L.append("- 없음 — 모든 불일치가 Tier·구역 경계 안에 머물렀다")
    L.append("")
    L.append("주의: v3 구역 비교는 완전히 대칭이 아니다 — Claude 분류는 경계 판정 축"
             "(unstable) 6개사를 기록했지만, Fable 1차 분류 세션은 대안 레벨을 "
             "기록하지 않아 구간 전파에 CONFIDENCE 만 남았다(ALT 는 재분류분 2건뿐). "
             "이 비대칭은 Fable 쪽 구간을 실제보다 좁게 만든다.")
    L.append("")

    L.append("## 3. 불일치 사례 대조표 (근거 문장)")
    L.append("")
    n_none = sum(1 for d in dis if (d["claude"] is None) != (d["fable"] is None))
    L.append(f"완전 불일치 {len(dis)}건. 그중 인접 허용(±1)으로도 해소되지 않는 것이 "
             f"{len(dis_far)}건 — `확인 필요` 대 레벨 {n_none}건 + 2단계 이상 차이 "
             f"{len(dis_far) - n_none}건. **불일치의 다수가 '레벨을 몇으로 매길까'가 "
             "아니라 '레벨을 매길 수 있는가'에서 갈렸다** — §4 증거 등급 규칙의 "
             "모호가 1차 원인이라는 뜻이다.")
    L.append("")
    L.append("| 기업 | 축 | Claude | Fable | Claude 근거 | Fable 근거 |")
    L.append("|---|---|---|---|---|---|")
    for d in dis:
        L.append(f"| {d['name']} | {rules.AXIS_LABELS[d['axis']]} | "
                 f"{_lv(d['claude'])} | {_lv(d['fable'])} | "
                 f"{d['claude_why']} | {d['fable_why']} |")
    L.append("")

    L.append("## 4. CONFIDENCE=low 와 실제 불일치의 겹침")
    L.append("")
    L.append(f"- low 표시 축: {conf['n_low']}개 / 실제 불일치: {conf['n_disagree']}개 / "
             f"겹침: {conf['n_overlap']}개")
    p = f"{conf['precision']:.0%}" if conf["precision"] is not None else "—"
    rc = f"{conf['recall']:.0%}" if conf["recall"] is not None else "—"
    L.append(f"- low 표시가 불일치를 맞힌 비율(정밀도): **{p}** / "
             f"불일치 중 low 로 예고된 비율(재현율): **{rc}**")
    L.append("")
    L.append("해석: 분류자는 자기 불확실성을 **부분적으로만** 안다. low 표시 축의 "
             "약 2/3 는 실제로 갈렸으므로 low → `판정 불안정`(unstable) 자동 생성은 "
             "유효한 신호다. 그러나 재현율이 절반이라 — 나머지 절반의 불일치는 "
             "분류자가 확신한 채 갈렸다(대부분 Team 축의 §4 규칙 해석 차이). "
             "low 표시만으로 불일치를 다 잡을 수는 없고, §4 규칙 명문화가 함께 필요한 "
             "이유다.")
    L.append("")

    L.append("## 5. 레벨 정의 개선 전후 (작업 2-3)")
    L.append("")
    if imp:
        L.append(f"- 재분류한 축: {imp['n_reclassified']}개 (불일치했던 축만 — "
                 "일치했던 축은 건드리지 않았다)")
        L.append(f"- 전체 인접 일치율: {imp['overall_before']['adjacent']:.0%} → "
                 f"**{imp['overall_after']['adjacent']:.0%}** / "
                 f"완전 일치율: {imp['overall_before']['exact']:.0%} → "
                 f"**{imp['overall_after']['exact']:.0%}** / "
                 f"κ: {imp['overall_before']['kappa']} → **{imp['overall_after']['kappa']}**")
        L.append(f"- 재분류 축만 보면: 인접 {imp['subset_before']['adjacent']:.0%} → "
                 f"**{imp['subset_after']['adjacent']:.0%}**, "
                 f"완전 {imp['subset_before']['exact']:.0%} → "
                 f"**{imp['subset_after']['exact']:.0%}**")
        L.append("- ⚠ 이 수치는 부분적으로 in-sample 이다: 개선된 §3·§4 의 판별 질문에는 "
                 "이번 20개사의 실제 사례가 예시로 붙어 있어, 재분류 세션이 예시로 "
                 "인용된 축은 규칙이 답을 직접 인코딩한다. 규칙이 일반화되는지는 "
                 "**새 기업**에서만 검증된다.")
        L.append("- 기준점(Claude 분류)은 고정한 채 Fable 쪽만 재분류했다. 남은 불일치 "
                 "상당수는 개선된 §4 가 금지하는 근거(프로그램 선발 이력·회사 조달 "
                 "실적을 팀 경력으로 인정)로 Claude 분류가 레벨을 부여한 축이다 — "
                 "즉 개선분을 Claude 분류에도 적용하면 일치율은 더 오를 것이나, "
                 "그것은 기존 분류의 수정이므로 이번 측정에서는 하지 않았다.")
    else:
        L.append("- (재분류 미수행)")
    L.append("")

    L.append("## 6. 분류자를 바꾸면 결론이 바뀌는가 (작업 3)")
    L.append("")
    L.append("사실·게이트·Fit·신뢰성은 고정하고 **레벨 분류만** 바꿔 실험 1·2 를 재실행했다. "
             "라벨 표본 10개사(합격 8 + 확정 불합격 2).")
    L.append("")
    L.append("| 지표 | Claude 분류 | Fable 원분류 | Fable 재분류(개선 후) |")
    L.append("|---|---|---|---|")
    cols = (swap["claude"], swap_raw["fable"], swap["fable"])
    for tag in ("v2", "v3"):
        cells = []
        for col in cols:
            d = col["exp2"][tag]
            acc = f"{d['accuracy']:.0%}" if d["accuracy"] is not None else "—"
            cells.append(f"{acc} / {d['coverage']:.0%} ({d['decided']}건)")
        L.append(f"| {tag} 확정 판정 (정확도 / 커버리지) | " + " | ".join(cells) + " |")
        L.append(f"| {tag} 틀린 단정 | " + " | ".join(
            ", ".join(col["exp2"][tag]["wrong"]) or "없음" for col in cols) + " |")
    L.append("| v2 합격사 유지 / 불합격사 검출 | " + " | ".join(
        f"{col['exp1']['v2']['admit_kept']} / {col['exp1']['v2']['reject_caught']}"
        for col in cols) + " |")
    L.append("| SaaSMetrics (v2 Tier · v3 구역) | " + " | ".join(
        f"{col['saasmetrics']['v2_tier']} · {col['saasmetrics']['v3_zone']}"
        for col in cols) + " |")
    L.append("")

    L.append("## 7. 결론 — 분류자에 따라 무엇이 바뀌고 무엇이 남는가")
    L.append("")
    L.append("1. **v2 의 확정 판정은 분류자 의존이다.** Claude 분류에서는 SaaSMetrics "
             "오탐(정확도 83%), Fable 원분류에서는 카드몬스터(실제 합격) 오탈락"
             "(정확도 67%) — 같은 규칙표가 분류자에 따라 반대 방향으로 틀린다. "
             "기존 리포트의 v2 수치(83%/60%)는 분류자 한 명의 값이다.")
    L.append("2. **v3 의 핵심 주장(단정한 것은 틀리지 않는다)은 세 분류 세트 모두에서 "
             "유지됐다.** 단정 건수·대상은 달라지지만(예: Neptune 이 Fable 분류에서 "
             "확정 추천 → 사람 검토) 틀린 단정은 어느 쪽에도 없다. 구조가 분류 "
             "불일치를 흡수한다 — 불일치 축의 대부분이 `확인 필요` 판단 차이라 "
             "구간 폭으로 전파되기 때문이다.")
    L.append("3. **SaaSMetrics 는 어느 분류에서도 `확정 추천`이 나오지 않았다.**")
    L.append("4. 완전 일치율 60%(κ 0.378)는 '같은 사실이면 같은 점수' 주장의 앞 절반"
             "(사실→레벨)이 **그대로는 재현되지 않음**을 뜻한다. §3·§4 개선 후 74%"
             "(κ 0.59)로 올랐으나 여전히 100%가 아니다 — 이 구간의 불일치는 v3 "
             "구간·`판정 불안정` 표기로 출력에 노출하는 것이 현재의 정직한 처리다.")
    L.append("")

    L.append("## 8. 작업 4 (음성 표본 확대) — 찾지 못했다")
    L.append("")
    L.append("확정 불합격 표본을 2개사에서 늘리기 위해 창업자가 스스로 공개한 탈락 "
             "사례를 검색했으나, **채택 기준(지원 시점의 트랙션·팀·제품 상태가 글에 "
             "명시 + 프로그램·시기 특정)을 충족하는 새 사례를 확보하지 못했다.**")
    L.append("")
    L.append("- Happyfeed(Matt Kandler) \"Rejection #9\" — 액셀러레이터 9회 탈락 공개. "
             "그러나 원문(Medium)이 접근 차단(403)이라 지원 시점 상태·프로그램명을 "
             "증거 등급 `문서 명시`로 확보 불가 → 제외.")
    L.append("- YC 라이브러리의 HAX 탈락 사례(기계식 휠체어, 피드백 \"defensible 하지 "
             "않다\") — 창업자·시기·지원 시점 트랙션 미명시 → 분류 불가로 제외.")
    L.append("- \"Rejected By YC\" 인터뷰 시리즈 — 후보군이나 개별 회차에서 지원 시점 "
             "상태를 추출·검증하는 작업이 남아 있음(후속 과제).")
    L.append("")
    L.append("따라서 **정밀도·특이도는 여전히 확정 불합격 2개사 기준으로 추정 불가**다. "
             "이 한계는 이번 측정으로 바뀌지 않았다.")
    L.append("")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--fable-reports", action="store_true",
                    help="Fable 분류 기준의 backtest/experiment 리포트 생성")
    a = ap.parse_args()
    rows = axis_pairs()
    r = rates(rows)
    print(f"완전 {r['exact']:.0%} / 인접 {r['adjacent']:.0%} / "
          f"None {r['none_agree']:.0%} / κ {r['kappa']} ({r['n_axes']}축)")
    for role, d in by_role(rows).items():
        print(f"  {role}: 완전 {d['exact']:.0%} / 인접 {d['adjacent']:.0%} (n={d['n']})")
    for d in tier_impact():
        print(f"  [영향] {d['name']}: v2 {d['tier_claude']} → {d['tier_fable']} / "
              f"v3 {d['zone_claude']} → {d['zone_fable']}")
    c = confidence_overlap(rows)
    print(f"CONFIDENCE low {c['n_low']} / 불일치 {c['n_disagree']} / "
          f"겹침 {c['n_overlap']} (정밀도 {c['precision']}, 재현율 {c['recall']})")
    if a.report:
        body = render()
        (BASE / "screening" / "AGREEMENT.md").write_text(body, encoding="utf-8")
        backtest.OUT_DIR.mkdir(parents=True, exist_ok=True)
        (backtest.OUT_DIR / "agreement.md").write_text(body, encoding="utf-8")
        print("\n리포트: screening/AGREEMENT.md")
    if a.fable_reports:
        from screening import experiment
        saved_levels = dataset.LEVELS_V2
        saved_unstable = {c.key: c.unstable for c in dataset.COMPANIES}
        dataset.LEVELS_V2 = merged_fable(bool(RECLASSIFIED))
        for c in dataset.COMPANIES:
            c.unstable = unstable_of(c.key)
        try:
            results = backtest.run()
            mt = backtest.metrics(results)
            backtest.OUT_DIR.mkdir(parents=True, exist_ok=True)
            (backtest.OUT_DIR / "backtest_report_fable.md").write_text(
                "> ⚠ 이 리포트는 **Fable 독립 분류(개선 후)** 기준이다 — "
                "levels_fable.py 참조. 기존 분류 기준은 backtest_report.md.\n\n"
                + backtest.render_report(results, mt), encoding="utf-8")
            (backtest.OUT_DIR / "experiment_fable.md").write_text(
                "> ⚠ 이 리포트는 **Fable 독립 분류(개선 후)** 기준이다.\n\n"
                + experiment.render(results), encoding="utf-8")
            print("리포트: output/screening/{backtest_report_fable,experiment_fable}.md")
        finally:
            dataset.LEVELS_V2 = saved_levels
            for c in dataset.COMPANIES:
                c.unstable = saved_unstable[c.key]


if __name__ == "__main__":
    main()
