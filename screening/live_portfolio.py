"""G5 — 실제 500/HAX 포트폴리오사 평가 (신규 크롤링).

  500 포트폴리오 15개사 (screening/data/portfolio_500.json) — 실제 500 투자 확인
  HAX 포트폴리오 12개사 (screening/data/portfolio_hax.json) — 실제 HAX 참여 확인

이들은 디캠프 배치사와 달리 **실제 500/HAX 가 투자·액셀러레이션한 기업**이라
'엔진이 실제 합격사를 어떻게 보는가'에 더 가깝다. 단 두 가지 주의:
  - 500 포트폴리오는 대부분 2013~2020 투자로 지금은 A 이후 단계다(스테이지가
    '지원 시점'이 아니라 '현재'다 → 후행 정보). 그래서 A 이후 게이트 사람 검토가
    많이 나오는데, 이는 "지금 지원하면 늦다"는 뜻이지 500 이 틀렸다는 뜻이 아니다.
  - HAX 포트폴리오는 프리시드~시드가 많아 스테이지 게이트를 잘 통과한다.

레벨은 levels_portfolio.py (격리 세션 분류)에서 읽고, levels_enriched 오버레이는
여기선 창업자 이력이 이미 founder_career 로 수집돼 분류에 반영됐으므로 생략한다.
"""
from __future__ import annotations

import json
from pathlib import Path

from screening import rules, rules_v2, rules_v3

DATA = Path(__file__).resolve().parent / "data"


def load_facts() -> dict:
    d = {}
    for f in ("portfolio_500.json", "portfolio_hax.json"):
        d.update(json.loads((DATA / f).read_text(encoding="utf-8")))
    return d


def _gate(track: str, band: str, key: str, facts: dict) -> tuple[str, bool, str]:
    gates = []
    if track == "500":
        gates.append(rules.GATE_PASS)                       # 제품 존재
        gates.append(rules.GATE_COND)                       # 풀타임/리로케이션
        gates.append(rules.GATE_HUMAN if band == "A 이후" else rules.GATE_PASS)
    else:  # hax
        gates.append(rules.GATE_PASS)                       # 제외 섹터 아님(HW)
        gates.append(rules.GATE_FAIL if band == "A 이후" else rules.GATE_COND)
        gates.append(rules.GATE_COND)                       # 캡테이블
    gates.append(rules.GATE_COND)                           # 영어
    verdict = rules.gate_verdict(
        [rules.GateResult("", v, "") for v in gates])
    scoreable = verdict != rules.GATE_FAIL
    outcome = {
        rules.GATE_FAIL: "게이트 탈락 (HAX 스테이지 이탈)",
        rules.GATE_HUMAN: "사람 검토 (500: A 이후 — 현재 후기단계)",
        rules.GATE_COND: "조건부 통과 → 점수화",
        rules.GATE_PASS: "통과 → 점수화",
    }[verdict]
    return verdict, scoreable, outcome


def rows(enrich: bool = True) -> list[dict]:
    facts = load_facts()
    try:
        from screening import levels_portfolio
        levels = levels_portfolio.LEVELS_PORTFOLIO
    except Exception:
        levels = {}
    out = []
    for key, f in facts.items():
        track = f["program"]
        band = f["stage_band"]
        gate, scoreable, outcome = _gate(track, band, key, f)
        prog = "실제 500 투자사" if track == "500" else "실제 HAX 참여사"
        row = {"group": "G5 실제 500/HAX 포트폴리오", "key": key, "name": f["name"],
               "tag": prog, "track": track, "band": band, "gate": gate,
               "note": outcome}
        lv = levels.get(key)
        if not scoreable or lv is None:
            row.update({"v2": "—", "v2w": None, "v3": "—",
                        "v3lo": None, "v3hi": None})
        else:
            lvl = {a: v[0] for a, v in lv.items()}
            unstable = {a: v[2] for a, v in lv.items()
                        if len(v) > 2 and v[2] is not None}
            g = rules.GATE_HUMAN if gate == rules.GATE_HUMAN else rules.GATE_COND
            v2 = rules_v2.aggregate(track, lvl)
            iv = rules_v3.decide(track, lvl, unstable, g)
            row.update({"v2": v2.tier, "v2w": v2.weighted, "v3": iv.zone,
                        "v3lo": iv.lo, "v3hi": iv.hi})
        out.append(row)
    return out


def funnel() -> list[dict]:
    facts = load_facts()
    out = []
    for key, f in facts.items():
        gate, scoreable, outcome = _gate(f["program"], f["stage_band"], key, f)
        out.append({"key": key, "name": f["name"], "batch": f["program"],
                    "track": f["program"], "band": f["stage_band"],
                    "gate": gate, "scoreable": scoreable, "outcome": outcome})
    return out


if __name__ == "__main__":
    from collections import Counter
    fr = funnel()
    print(f"G5 포트폴리오 {len(fr)}개사")
    for o, n in Counter(r["outcome"] for r in fr).most_common():
        print(f"  {n:2} {o}")
