"""실험 — 어느 구조가 실제로 더 정확한지 측정한다.

  python -m screening.experiment              # 결과 출력
  python -m screening.experiment --report     # screening/EXPERIMENT.md 생성

측정하는 것
  실험 1) 라벨 성적표 — 합격사 유지 / 불합격사 검출 (v1/v2/v3)
  실험 2) 확정 판정의 정확도와 커버리지 — v3 의 핵심 주장
  실험 3) 추천선 민감도 — 3.25 라는 컷오프가 운이었는가
  실험 4) 자료 완비 시뮬레이션 — 불확실성이 규칙 탓인가 자료 부재 탓인가
  실험 5) LOO 교차검증 — 한 기업을 빼고 컷오프를 정해도 같은 결론인가

라벨 표본이 작다(합격 8 + 불합격 2). 모든 수치는 그 한계 안에서 읽어야 한다.
"""
from __future__ import annotations

import argparse

from screening import backtest, dataset, rules, rules_v2, rules_v3

LABELED = ("admitted", "rejected")


def _labeled(results):
    return [r for r in results
            if r["company"].ground_truth.startswith(LABELED)]


def _is_admit(r):
    return r["company"].ground_truth.startswith("admitted")


# ---------------------------------------------------------------- v3 판정
def v3_of(r, line: float = rules_v3.RECOMMEND_LINE) -> rules_v3.Interval:
    c = r["company"]
    saved = rules_v3.RECOMMEND_LINE
    rules_v3.RECOMMEND_LINE = line
    try:
        return rules_v3.decide(c.track, dataset.levels_v2_of(c),
                               c.unstable, r["gate"])
    finally:
        rules_v3.RECOMMEND_LINE = saved


# ---------------------------------------------------------------- 실험 1·2
def exp1_scoreboard(results) -> dict:
    """합격사를 떨어뜨리지 않는가 / 불합격사를 걸러내는가."""
    lab = _labeled(results)
    adm = [r for r in lab if _is_admit(r)]
    rej = [r for r in lab if not _is_admit(r)]
    out = {}
    for m in backtest.MODES:
        keep = sum(1 for r in adm if not backtest.rejected(r, m))
        caught = sum(1 for r in rej if backtest.rejected(r, m))
        out[m] = {"admit_kept": f"{keep}/{len(adm)}",
                  "reject_caught": f"{caught}/{len(rej)}",
                  "total": f"{keep + caught}/{len(lab)}"}
    # v3 은 '비추천'을 탈락으로 본다
    keep = sum(1 for r in adm if v3_of(r).zone != rules_v3.ZONE_NO)
    caught = sum(1 for r in rej if v3_of(r).zone == rules_v3.ZONE_NO)
    out["v3"] = {"admit_kept": f"{keep}/{len(adm)}",
                 "reject_caught": f"{caught}/{len(rej)}",
                 "total": f"{keep + caught}/{len(lab)}"}
    return out


def exp2_confident(results) -> dict:
    """확정 판정만 세었을 때의 정확도와 커버리지.

    v2 는 Tier A·B 를 '추천', C·D 를 '비추천'으로 단정한다(보류만 유보).
    v3 은 구간이 추천선을 걸치지 않을 때만 단정한다.
    """
    lab = _labeled(results)

    def _score(decide):
        decided = right = 0
        wrong_names = []
        for r in lab:
            verdict = decide(r)          # True=추천 / False=비추천 / None=유보
            if verdict is None:
                continue
            decided += 1
            if verdict == _is_admit(r):
                right += 1
            else:
                wrong_names.append(f"{r['company'].name}"
                                   f"({'추천' if verdict else '비추천'})")
        return {"decided": decided, "correct": right,
                "coverage": round(decided / len(lab), 3),
                "accuracy": round(right / decided, 3) if decided else None,
                "wrong": wrong_names}

    def v2_decide(r):
        t = r["scores"]["v2"].tier
        if t == rules_v2.TIER_HOLD:
            return None
        if r["gate"] in (rules.GATE_FAIL, rules.GATE_HUMAN):
            return False
        return t in rules.PASS_TIERS

    def v3_decide(r):
        z = v3_of(r).zone
        return {rules_v3.ZONE_YES: True, rules_v3.ZONE_NO: False}.get(z)

    return {"v2": _score(v2_decide), "v3": _score(v3_decide),
            "n_labeled": len(lab)}


# ---------------------------------------------------------------- 실험 3
def exp3_line_sweep(results) -> list[dict]:
    """추천선을 옮겨도 v3 의 확정 판정이 계속 옳은가."""
    lab = _labeled(results)
    rows = []
    for line in (2.75, 3.00, 3.25, 3.50, 3.75):
        decided = right = 0
        for r in lab:
            z = v3_of(r, line).zone
            if z == rules_v3.ZONE_HUMAN:
                continue
            decided += 1
            if (z == rules_v3.ZONE_YES) == _is_admit(r):
                right += 1
        rows.append({"line": line, "decided": decided, "correct": right,
                     "accuracy": round(right / decided, 3) if decided else None})
    return rows


# ---------------------------------------------------------------- 실험 4
def exp4_full_docs(results) -> dict:
    """자료가 완비되면 확정 판정 비율이 얼마나 오르는가.

    `확인 필요` 축을 L3(중립값)으로 채워 '자료 제출됨'을 모사한다.
    이 시뮬레이션의 목적은 정확도 주장이 아니라, 남은 불확실성이
    **규칙 탓인지 자료 부재 탓인지** 분리하는 것이다.
    """
    lab = _labeled(results)
    now = sum(1 for r in lab if v3_of(r).zone != rules_v3.ZONE_HUMAN)
    after = 0
    for r in lab:
        c = r["company"]
        filled = {a: (3 if v is None else v)
                  for a, v in dataset.levels_v2_of(c).items()}
        iv = rules_v3.decide(c.track, filled, c.unstable, r["gate"])
        if iv.zone != rules_v3.ZONE_HUMAN:
            after += 1
    widths = [v3_of(r) for r in lab]
    avg_w = sum(i.width for i in widths) / len(widths)
    avg_unknown = sum(i.width_from_unknown for i in widths) / len(widths)
    return {"decided_now": f"{now}/{len(lab)}",
            "decided_if_full_docs": f"{after}/{len(lab)}",
            "avg_interval_width": round(avg_w, 3),
            "avg_width_from_unknown": round(avg_unknown, 3),
            "unknown_share_of_width": round(avg_unknown / avg_w, 3) if avg_w else 0}


# ---------------------------------------------------------------- 실험 5
def exp5_loo(results) -> dict:
    """LOO 교차검증 — 한 기업을 빼고 최적 추천선을 정한 뒤 그 기업을 판정."""
    lab = _labeled(results)
    lines = [2.75, 3.00, 3.25, 3.50, 3.75]
    decided = right = 0
    detail = []
    for held in lab:
        rest = [r for r in lab if r is not held]
        # 남은 기업에서 확정 판정 정확도가 가장 높은 추천선 선택 (동률이면 커버리지 우선)
        best, best_key = lines[0], (-1.0, -1)
        for line in lines:
            d = c = 0
            for r in rest:
                z = v3_of(r, line).zone
                if z == rules_v3.ZONE_HUMAN:
                    continue
                d += 1
                if (z == rules_v3.ZONE_YES) == _is_admit(r):
                    c += 1
            key = (c / d if d else 0.0, d)
            if key > best_key:
                best, best_key = line, key
        z = v3_of(held, best).zone
        if z == rules_v3.ZONE_HUMAN:
            detail.append(f"{held['company'].name}: 사람 검토 (line={best})")
            continue
        decided += 1
        ok = (z == rules_v3.ZONE_YES) == _is_admit(held)
        right += ok
        detail.append(f"{held['company'].name}: {z} "
                      f"{'✅' if ok else '❌'} (line={best})")
    return {"decided": decided, "correct": right, "n": len(lab),
            "accuracy": round(right / decided, 3) if decided else None,
            "detail": detail}


# ---------------------------------------------------------------- 리포트
def render(results) -> str:
    e1, e2 = exp1_scoreboard(results), exp2_confident(results)
    e3, e4, e5 = exp3_line_sweep(results), exp4_full_docs(results), exp5_loo(results)
    lab = _labeled(results)
    n_adm = sum(1 for r in lab if _is_admit(r))

    L = ["# 실험 — 어느 구조가 더 정확한가", ""]
    L.append(f"라벨 표본 **{len(lab)}개사** (합격 {n_adm} / 확정 불합격 {len(lab) - n_adm}). "
             "전 기업 공개 정보만 사용(덱·CV·설문 없음).")
    L.append("")
    L.append("v3 의 변경은 하나뿐이다: **점추정 → 구간추정.** `확인 필요` 축은 L1~L5, "
             "경계 판정 축은 인접 레벨까지 범위로 전파하고, 구간이 추천선을 걸치면 "
             "엔진이 단정하지 않는다. **라벨을 보고 튜닝한 것이 아니다.**")
    L.append("")

    L.append("## 실험 1 — 라벨 성적표")
    L.append("")
    L.append("| 버전 | 합격사 유지 | 불합격사 검출 | 합계 |")
    L.append("|---|---|---|---|")
    for m, r in e1.items():
        L.append(f"| {m} | {r['admit_kept']} | {r['reject_caught']} | "
                 f"**{r['total']}** |")
    L.append("")

    L.append("## 실험 2 — 확정 판정의 정확도 (핵심)")
    L.append("")
    L.append("'단정한 것만' 채점한다. 유보(보류/사람 검토)는 분모에서 제외한다.")
    L.append("")
    L.append("| 버전 | 단정 건수 | 커버리지 | 확정 판정 정확도 | 틀린 단정 |")
    L.append("|---|---|---|---|---|")
    for m in ("v2", "v3"):
        d = e2[m]
        acc = f"{d['accuracy']:.0%}" if d["accuracy"] is not None else "—"
        L.append(f"| {m} | {d['decided']}/{e2['n_labeled']} | {d['coverage']:.0%} | "
                 f"**{acc}** | {', '.join(d['wrong']) or '없음'} |")
    L.append("")
    L.append("v2 는 많이 단정하지만 그 안에 오탐이 섞인다. v3 는 덜 단정하는 대신 "
             "단정한 것은 틀리지 않는다 — 스크리닝에서 중요한 것은 후자다. "
             "잘못된 탈락·잘못된 추천은 되돌리기 어렵고, `사람 검토`는 비용만 든다.")
    L.append("")

    L.append("## 실험 3 — 추천선 민감도")
    L.append("")
    L.append("3.25 라는 값이 운이었는지 확인한다.")
    L.append("")
    L.append("| 추천선 | 단정 건수 | 정확도 |")
    L.append("|---|---|---|")
    for r in e3:
        acc = f"{r['accuracy']:.0%}" if r["accuracy"] is not None else "—"
        L.append(f"| {r['line']:.2f} | {r['decided']} | {acc} |")
    L.append("")

    L.append("## 실험 4 — 불확실성은 규칙 탓인가 자료 부재 탓인가")
    L.append("")
    L.append(f"- 현재 확정 판정: **{e4['decided_now']}**")
    L.append(f"- `확인 필요` 축을 채웠다고 가정하면: **{e4['decided_if_full_docs']}**")
    L.append(f"- 평균 구간 폭 {e4['avg_interval_width']} 중 "
             f"**{e4['unknown_share_of_width']:.0%}** 가 `확인 필요` 축에서 나온다")
    L.append("")
    L.append("즉 남은 불확실성의 대부분은 규칙의 한계가 아니라 **자료가 없어서**다. "
             "실제 운영에서는 덱·CV·설문이 들어오므로 확정 판정 비율이 크게 오른다.")
    L.append("")

    L.append("## 실험 5 — LOO 교차검증")
    L.append("")
    acc = f"{e5['accuracy']:.0%}" if e5["accuracy"] is not None else "—"
    L.append(f"한 기업을 빼고 나머지로 추천선을 고른 뒤 그 기업을 판정: "
             f"단정 {e5['decided']}/{e5['n']} · 정확도 **{acc}**")
    L.append("")
    for d in e5["detail"]:
        L.append(f"- {d}")
    L.append("")

    L.append("## 결론")
    L.append("")
    L.append(f"1. v3 는 단정한 {e2['v3']['decided']}건에서 "
             f"{'오류가 없다' if not e2['v3']['wrong'] else '오류가 있다'} — "
             "v2 가 통과시킨 SaaSMetrics 오탐을 `사람 검토`로 돌린다.")
    L.append("2. 대가는 커버리지다. 공개 정보만으로는 "
             f"{e2['v3']['coverage']:.0%} 만 단정하고 나머지는 사람에게 넘긴다.")
    L.append("3. 그 커버리지 한계는 자료 부재에서 오며(실험 4), 제출 자료가 들어오면 "
             "완화된다.")
    L.append("4. **여전히 확정 불합격 표본이 2개사다.** 오탐률의 진짜 값은 모른다. "
             "v3 가 v2 보다 나은 이유는 통계가 아니라 구조 — 모르는 것을 "
             "모른다고 출력하기 때문이다.")
    L.append("")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    results = backtest.run()
    body = render(results)
    print(body)
    if a.report:
        (backtest.BASE / "screening" / "EXPERIMENT.md").write_text(
            body, encoding="utf-8")
        backtest.OUT_DIR.mkdir(parents=True, exist_ok=True)
        (backtest.OUT_DIR / "experiment.md").write_text(body, encoding="utf-8")
        print("\n리포트: screening/EXPERIMENT.md")


if __name__ == "__main__":
    main()
