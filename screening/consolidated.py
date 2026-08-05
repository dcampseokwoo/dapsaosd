"""전체 평가 통합 — 모든 출처의 기업을 하나의 워크북으로.

  python -m screening.consolidated            # 통합 퍼널 요약
  python -m screening.consolidated --xlsx     # output/screening/engine_full_eval.xlsx

출처(그룹)
  G1 실전 500 선발 (딥크롤 보강)  : 카드몬스터·올세일 — live_eval.ENRICHED
  G2 500/HAX 라벨·대조 표본       : dataset.COMPANIES 중 G1 제외 18개사 (라벨 있음)
  G3 디캠프 배치 2·4·6·7기        : live_batch (31개사)
  G4 디캠프 배치 1·3·5기          : live_batch2 (신규 크롤링)

카드몬스터·올세일은 G1(딥크롤 보강판)으로 한 번만 넣는다. dataset 의 공개정보판과
중복 계상하지 않기 위해 G2 에서 제외한다.
"""
from __future__ import annotations

import argparse

from screening import backtest, dataset, rules, rules_v2, rules_v3

# G1: 딥크롤 보강 실전 선발
G1_KEYS = ("cardmonster", "allsale")


def _v2v3(track, levels, unstable, gate):
    v2 = rules_v2.aggregate(track, levels)
    v3 = rules_v3.decide(track, levels, unstable, gate)
    return v2, v3


def group1() -> list[dict]:
    from screening import live_eval
    out = []
    for k in G1_KEYS:
        r = live_eval.evaluate(k)
        out.append({
            "group": "G1 실전 500 선발(딥크롤)", "key": k, "name": r["e"]["name"],
            "tag": "500 실제선발 ✅", "track": r["e"]["track"], "band": r["e"]["stage_band"],
            "gate": r["gate"], "v2": r["v2"].tier, "v2w": r["v2"].weighted,
            "v3": r["v3"].zone, "v3lo": r["v3"].lo, "v3hi": r["v3"].hi,
            "note": r["e"]["selected"]})
    return out


def group2() -> list[dict]:
    gt_label = {"admitted_500": "500 합격", "admitted_hax": "HAX 합격",
                "rejected_500": "500 탈락", "rejected_multi": "복수AC 탈락",
                "unknown": "미확인 대조", "probe": "게이트 검증"}
    out = []
    for c in dataset.COMPANIES:
        if c.key in G1_KEYS:
            continue
        r = backtest.evaluate(c)
        if r["routed"]:
            out.append({"group": "G2 라벨·대조 표본", "key": c.key, "name": c.name,
                        "tag": gt_label[c.ground_truth], "track": c.track,
                        "band": c.stage_band, "gate": "라우팅", "v2": "—", "v2w": None,
                        "v3": "라우팅", "v3lo": None, "v3hi": None,
                        "note": "바이오 → IndieBio"})
            continue
        v2, iv = r["scores"]["v2"], r["v3"]
        out.append({"group": "G2 라벨·대조 표본", "key": c.key, "name": c.name,
                    "tag": gt_label[c.ground_truth], "track": c.track,
                    "band": c.stage_band, "gate": r["gate"], "v2": v2.tier,
                    "v2w": v2.weighted, "v3": iv.zone if iv else "—",
                    "v3lo": iv.lo if iv else None, "v3hi": iv.hi if iv else None,
                    "note": f"정답: {gt_label[c.ground_truth]}"})
    return out


def _batch_rows(mod, levels_mod, group_label) -> list[dict]:
    """live_batch / live_batch2 공통 — 라우팅 퍼널 + 점수화."""
    out = []
    lv_all = getattr(levels_mod, "LEVELS", {})
    for fr in mod.funnel():
        row = {"group": group_label, "key": fr["key"], "name": fr["name"],
               "tag": f"디캠프 배치 {fr['batch']}", "track": fr["track"],
               "band": fr["band"], "gate": fr["gate"], "note": fr["outcome"]}
        lv = lv_all.get(fr["key"])
        if fr["track"] == "bio_routing" or not fr["scoreable"] or lv is None:
            row.update({"v2": "—", "v2w": None, "v3": "—", "v3lo": None, "v3hi": None})
        else:
            levels = {a: v[0] for a, v in lv.items()}
            unstable = {a: v[2] for a, v in lv.items()
                        if len(v) > 2 and v[2] is not None}
            gate = (rules.GATE_HUMAN if fr["gate"] == rules.GATE_HUMAN
                    else rules.GATE_COND)
            v2, iv = _v2v3(fr["track"], levels, unstable, gate)
            row.update({"v2": v2.tier, "v2w": v2.weighted, "v3": iv.zone,
                        "v3lo": iv.lo, "v3hi": iv.hi})
        out.append(row)
    return out


def group3() -> list[dict]:
    from screening import live_batch, levels_live
    lm = type("LM", (), {"LEVELS": levels_live.LEVELS_LIVE})
    return _batch_rows(live_batch, lm, "G3 디캠프 배치 2·4·6·7기")


def group4() -> list[dict]:
    try:
        from screening import live_batch2, levels_live2
    except Exception:
        return []
    lm = type("LM", (), {"LEVELS": levels_live2.LEVELS_LIVE2})
    return _batch_rows(live_batch2, lm, "G4 디캠프 배치 1·3·5기")


def all_rows() -> list[dict]:
    return group1() + group2() + group3() + group4()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", action="store_true")
    a = ap.parse_args()
    rows = all_rows()
    from collections import Counter
    print(f"전체 평가 기업: {len(rows)}개사")
    for g, n in Counter(r["group"] for r in rows).items():
        print(f"  {n:2} {g}")
    print()
    gate = Counter(r["gate"] for r in rows)
    for k, n in gate.most_common():
        print(f"  게이트 {k}: {n}")
    if a.xlsx:
        from screening import consolidated_xlsx
        print("\n" + str(consolidated_xlsx.build()))


if __name__ == "__main__":
    main()
