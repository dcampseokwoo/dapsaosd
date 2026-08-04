"""프리스크리닝 엔진 백테스트 실행기.

  python -m screening.backtest              # 표 + 지표 출력
  python -m screening.backtest --report     # output/screening/ + screening/RESULTS.md 생성

네트워크·API 키 불필요. 웹 검색으로 수집한 팩트(dataset.py)를 고정 규칙
테이블(rules.py)에 통과시켜, 엔진이 실제로 기업을 '걸러내는지'를 측정한다.

측정 항목
  1) 판정 분포 — 전부 같은 칸에 몰리면 스크리너로서 무용
  2) 재현율   — 실제 500/HAX 합격 기업을 추천으로 잡아내는가
  3) 게이트   — 스테이지 이탈·제외 섹터·바이오 라우팅이 실제로 작동하는가
  4) 민감도   — 경계 판정 축을 한 단계 뒤집으면 Tier 가 바뀌는가(결정성 취약점)
  5) 모드 격차 — `확인 필요` 해석(strict/neutral)에 따라 판정이 얼마나 갈리는가
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from screening import dataset, rules

BASE = Path(__file__).resolve().parent.parent
OUT_DIR = BASE / "output" / "screening"
MODES = ("strict", "neutral")


# ---------------------------------------------------------------- 실행
def evaluate(c: dataset.Company) -> dict:
    """한 기업에 대해 게이트 → 신뢰성 → 두 모드 점수 → 2×2 판정."""
    if c.track == "bio_routing":
        return {
            "company": c, "routed": True, "gates": [], "gate": "라우팅",
            "credibility": "해당 없음", "scores": {},
            "verdict": {m: "점수 미산출 (SOSV IndieBio 안내)" for m in MODES},
        }

    gates = rules.run_gates(c)
    gate = rules.gate_verdict(gates)
    cred = rules.credibility_overall(c.credibility)
    scores = {m: rules.aggregate(c.track, c.levels_only, m, cred) for m in MODES}

    verdict = {}
    for m in MODES:
        tier = scores[m].tier
        if gate == rules.GATE_FAIL:
            verdict[m] = f"게이트 탈락 (참고 Tier {_short(tier)})"
        elif gate == rules.GATE_HUMAN:
            verdict[m] = f"사람 검토 (참고 Tier {_short(tier)})"
        else:
            verdict[m] = tier
    return {"company": c, "routed": False, "gates": gates, "gate": gate,
            "credibility": cred, "scores": scores, "verdict": verdict}


def _short(tier: str) -> str:
    """'B 확인 후 추천' → 'B', '판정 불가' → '판정 불가'."""
    return tier[0] if tier[:1] in ("A", "B", "C", "D") else tier


def recommended(res: dict, mode: str) -> bool:
    """'추천 대상'인가 = 게이트 통과/조건부 + Tier A·B."""
    if res["routed"] or res["gate"] in (rules.GATE_FAIL, rules.GATE_HUMAN):
        return False
    return res["scores"][mode].tier in rules.PASS_TIERS


def sensitivity(c: dataset.Company, mode: str) -> list[str]:
    """경계 판정 축을 대안 레벨로 뒤집었을 때 Tier 가 바뀌는지."""
    if not c.unstable or c.track == "bio_routing":
        return []
    base = rules.aggregate(c.track, c.levels_only, mode,
                           rules.credibility_overall(c.credibility)).tier
    flips = []
    for axis, alt in c.unstable.items():
        lv = dict(c.levels_only)
        lv[axis] = alt
        t = rules.aggregate(c.track, lv, mode,
                            rules.credibility_overall(c.credibility)).tier
        if t != base:
            flips.append(f"{rules.AXIS_LABELS[axis]} L{c.levels_only[axis]}→L{alt}: "
                         f"{_short(base)}→{_short(t)}")
    return flips


def run() -> list[dict]:
    return [evaluate(c) for c in dataset.COMPANIES]


# ---------------------------------------------------------------- 지표
def metrics(results: list[dict]) -> dict:
    scored = [r for r in results if not r["routed"]]
    out: dict = {"n_total": len(results), "n_scored": len(scored), "modes": {}}

    for m in MODES:
        dist: dict[str, int] = {}
        for r in scored:
            dist[r["verdict"][m]] = dist.get(r["verdict"][m], 0) + 1
        rec = [r for r in scored if recommended(r, m)]
        admits = [r for r in scored
                  if r["company"].ground_truth.startswith("admitted")]
        hit = [r for r in admits if recommended(r, m)]
        out["modes"][m] = {
            "distribution": dist,
            "recommended": [r["company"].name for r in rec],
            "pass_rate": round(len(rec) / len(scored), 3),
            "admit_recall": f"{len(hit)}/{len(admits)}",
            "admit_missed": [r["company"].name for r in admits
                             if not recommended(r, m)],
        }

    # 모드 간 판정 불일치
    out["mode_disagreement"] = [
        {"name": r["company"].name,
         "strict": r["verdict"]["strict"], "neutral": r["verdict"]["neutral"]}
        for r in scored if r["verdict"]["strict"] != r["verdict"]["neutral"]
    ]
    # 민감도 (strict 기준)
    out["sensitivity"] = [
        {"name": r["company"].name, "flips": f}
        for r in scored if (f := sensitivity(r["company"], "strict"))
    ]
    # 게이트 프로브
    out["gates"] = [
        {"name": r["company"].name, "track": r["company"].track,
         "verdict": r["gate"],
         "fired": [f"{g.name}={g.verdict}" for g in r["gates"]
                   if g.verdict != rules.GATE_PASS]}
        for r in results
    ]
    return out


# ---------------------------------------------------------------- 출력
def _tier_cell(res: dict, mode: str) -> str:
    if res["routed"]:
        return "라우팅"
    s = res["scores"][mode]
    w = "—" if s.weighted is None else f"{s.weighted:.2f}"
    return f"{res['verdict'][mode]} ({w})"


def render_table(results: list[dict]) -> str:
    lines = [
        "| 기업 | 트랙 | 스테이지 | 정답 | 게이트 | strict | neutral | Fit |",
        "|---|---|---|---|---|---|---|---|",
    ]
    gt = {"admitted_500": "합격(500)", "admitted_hax": "합격(HAX)",
          "unknown": "미확인", "probe": "게이트 검증"}
    for r in results:
        c = r["company"]
        lines.append(
            f"| {c.name} | {c.track} | {c.stage_band} | {gt[c.ground_truth]} | "
            f"{r['gate']} | {_tier_cell(r, 'strict')} | {_tier_cell(r, 'neutral')} | "
            f"{c.fit} |")
    return "\n".join(lines)


def render_report(results: list[dict], mt: dict) -> str:
    L = ["# 프리스크리닝 엔진 백테스트 — 500 Global / HAX", ""]
    L.append(f"- 대상: {mt['n_total']}개사 (점수 산출 {mt['n_scored']}개사 + 바이오 라우팅)")
    L.append("- 입력: 웹 검색으로 수집한 공개 정보만 (피치덱·CV·설문 없음 → 전 기업 `간이 진단`)")
    L.append("- 점수 계산: `screening/rules.py` 고정 테이블. 사실→레벨 분류는 "
             "`screening/dataset.py` 에 근거와 함께 기록")
    L.append("")
    L.append("## 1. 전체 판정표")
    L.append("")
    L.append(render_table(results))
    L.append("")

    L.append("## 2. 판정 분포와 통과율")
    for m in MODES:
        d = mt["modes"][m]
        L.append(f"\n### `{m}` 모드")
        L.append("")
        for k, v in sorted(d["distribution"].items(), key=lambda x: -x[1]):
            L.append(f"- {k}: {v}개사")
        L.append(f"- **추천 대상 비율: {d['pass_rate']:.0%}** "
                 f"({', '.join(d['recommended']) or '없음'})")
        L.append(f"- 실제 합격 기업 재현율: **{d['admit_recall']}**"
                 + (f" — 놓친 기업: {', '.join(d['admit_missed'])}"
                    if d["admit_missed"] else ""))
    L.append("")

    L.append("## 3. `확인 필요` 해석에 따른 판정 격차")
    L.append("")
    L.append("프롬프트 운영원칙1(불명=감점 금지)과 레벨표(증거 없으면 하위 레벨)가 "
             "충돌해, 같은 사실에서 두 개의 정답이 나온다.")
    L.append("")
    if mt["mode_disagreement"]:
        L.append("| 기업 | strict | neutral |")
        L.append("|---|---|---|")
        for d in mt["mode_disagreement"]:
            L.append(f"| {d['name']} | {d['strict']} | {d['neutral']} |")
    else:
        L.append("- 불일치 없음")
    L.append("")

    L.append("## 4. 결정성 민감도 (경계 판정 1단계 뒤집기)")
    L.append("")
    if mt["sensitivity"]:
        for s in mt["sensitivity"]:
            L.append(f"- **{s['name']}**: {'; '.join(s['flips'])}")
    else:
        L.append("- Tier 를 바꾸는 경계 판정 없음")
    L.append("")

    L.append("## 5. 하드 게이트 작동 확인")
    L.append("")
    L.append("| 기업 | 트랙 | 종합 | 발동한 게이트 |")
    L.append("|---|---|---|---|")
    for g in mt["gates"]:
        L.append(f"| {g['name']} | {g['track']} | {g['verdict']} | "
                 f"{', '.join(g['fired']) or '—'} |")
    L.append("")

    L.append("## 6. 기업별 축 레벨과 근거")
    for r in results:
        c = r["company"]
        L.append(f"\n### {c.name} — {c.sector_note}")
        L.append("")
        if r["routed"]:
            L.append("- **라우팅**: 바이오 → 점수 미산출, SOSV IndieBio NY/SF 안내")
        else:
            for axis, (lv, why) in c.levels.items():
                tag = f"L{lv}" if lv else "`확인 필요`"
                L.append(f"- **{rules.AXIS_LABELS[axis]}** {tag} — {why}")
            L.append(f"- 신뢰성: {r['credibility']}")
        L.append(f"- Fit **{c.fit}** — {c.fit_reason}")
        if c.needs_confirm:
            L.append(f"- `확인 필요`: {', '.join(c.needs_confirm)}")
        if c.note:
            L.append(f"- 비고: {c.note}")
        if c.sources:
            L.append("- 출처: " + " / ".join(c.sources))
    L.append("")

    L.append("## 7. 프롬프트 미정의 항목 (이 백테스트에서 보충한 값)")
    L.append("")
    for g in rules.SPEC_GAPS:
        L.append(f"- {g}")
    L.append("")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="리포트 파일 생성")
    a = ap.parse_args()

    results = run()
    mt = metrics(results)
    print(render_table(results))
    print()
    for m in MODES:
        d = mt["modes"][m]
        print(f"[{m}] 통과율 {d['pass_rate']:.0%} / 합격기업 재현율 {d['admit_recall']}")
    print(f"[모드 불일치] {len(mt['mode_disagreement'])}개사")

    if a.report:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        body = render_report(results, mt)
        (OUT_DIR / "backtest_report.md").write_text(body, encoding="utf-8")
        (OUT_DIR / "backtest_metrics.json").write_text(
            json.dumps(mt, ensure_ascii=False, indent=2), encoding="utf-8")
        (BASE / "screening" / "RESULTS.md").write_text(body, encoding="utf-8")
        print(f"\n리포트: {OUT_DIR/'backtest_report.md'}, screening/RESULTS.md")


if __name__ == "__main__":
    main()
