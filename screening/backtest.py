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

from screening import dataset, rules, rules_v2

BASE = Path(__file__).resolve().parent.parent
OUT_DIR = BASE / "output" / "screening"
MODES = ("strict", "neutral", "v2")


# ---------------------------------------------------------------- 실행
def evaluate(c: dataset.Company) -> dict:
    """한 기업에 대해 게이트 → 신뢰성 → 두 모드 점수 → 2×2 판정."""
    if c.track == "bio_routing":
        return {
            "company": c, "routed": True, "gates": [], "gate": "라우팅",
            "credibility": "해당 없음", "scores": {},
            "verdict": {m: "점수 미산출 (SOSV IndieBio 안내)" for m in MODES},
            "fit": "해당 없음", "fit_score": 0, "fit_notes": [],
            "action": rules_v2.action_of("", "", "라우팅", True),
        }

    gates = rules.run_gates(c)
    gate = rules.gate_verdict(gates)
    cred = rules.credibility_overall(c.credibility)
    scores = {m: rules.aggregate(c.track, c.levels_only, m, cred)
              for m in ("strict", "neutral")}
    scores["v2"] = rules_v2.aggregate(c.track, dataset.levels_v2_of(c), cred)

    verdict = {}
    for m in MODES:
        tier = scores[m].tier
        if gate == rules.GATE_FAIL:
            verdict[m] = f"게이트 탈락 (참고 Tier {_short(tier)})"
        elif gate == rules.GATE_HUMAN:
            verdict[m] = f"사람 검토 (참고 Tier {_short(tier)})"
        else:
            verdict[m] = tier
    # v2 구조: Fit 도 규칙표가 계산한다 (v1 은 정성 판단이라 결정성이 없었다)
    fit, fit_score, fit_notes = rules_v2.fit_of(dataset.FIT.get(c.key, {}), gate)
    action = rules_v2.action_of(scores["v2"].tier, fit, gate, False)
    return {"company": c, "routed": False, "gates": gates, "gate": gate,
            "credibility": cred, "scores": scores, "verdict": verdict,
            "fit": fit, "fit_score": fit_score, "fit_notes": fit_notes,
            "action": action}


def _short(tier: str) -> str:
    """'B 확인 후 추천' → 'B', '판정 보류 — 정보 부족' → '보류'."""
    if tier[:1] in ("A", "B", "C", "D"):
        return tier[0]
    return "보류" if tier.startswith("판정 보류") else tier


def recommended(res: dict, mode: str) -> bool:
    """'추천 대상'인가 = 게이트 통과/조건부 + Tier A·B."""
    if res["routed"] or res["gate"] in (rules.GATE_FAIL, rules.GATE_HUMAN):
        return False
    return res["scores"][mode].tier in rules.PASS_TIERS


def rejected(res: dict, mode: str) -> bool:
    """'탈락 처리'인가 = 게이트 탈락 또는 Tier C/D.

    `판정 보류`는 탈락이 아니다 — 설문·증빙을 받으면 다시 평가되는 상태다.
    """
    if res["routed"]:
        return False
    if res["gate"] == rules.GATE_FAIL:
        return True
    tier = res["scores"][mode].tier
    return tier.startswith(("C", "D"))


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
            "admit_rejected": [r["company"].name for r in admits
                               if rejected(r, m)],
            "n_hold": sum(1 for r in scored
                          if r["scores"][m].tier == rules_v2.TIER_HOLD),
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
    if s.weighted is None:
        # 점수 미산출(보류/판정 불가) — 긴 Tier 명을 줄여 표를 읽기 쉽게
        return res["verdict"][mode].replace(s.tier, _short(s.tier))
    return f"{res['verdict'][mode]} ({s.weighted:.2f})"


def render_table(results: list[dict]) -> str:
    lines = [
        "| 기업 | 트랙 | 스테이지 | 정답 | 게이트 | v1 strict | v1 neutral | **v2** | Fit |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    gt = {"admitted_500": "합격(500)", "admitted_hax": "합격(HAX)",
          "rejected_500": "**탈락(500)**", "rejected_multi": "**탈락(복수AC)**",
          "unknown": "미확인", "probe": "게이트 검증"}
    for r in results:
        c = r["company"]
        lines.append(
            f"| {c.name} | {c.track} | {c.stage_band} | {gt[c.ground_truth]} | "
            f"{r['gate']} | {_tier_cell(r, 'strict')} | {_tier_cell(r, 'neutral')} | "
            f"**{_tier_cell(r, 'v2')}** | {r['fit']} |")
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
        L.append(f"- 합격 기업 **오탈락**(C/D·게이트탈락 처리): "
                 f"**{len(d['admit_rejected'])}개사**"
                 + (f" — {', '.join(d['admit_rejected'])}"
                    if d["admit_rejected"] else ""))
        if d["n_hold"]:
            L.append(f"- 판정 보류(설문·증빙 요청): {d['n_hold']}개사")
    L.append("")

    L.append("## 2-1. v1 → v2 수정 효과")
    L.append("")
    L.append("v2 는 가중치를 건드리지 않고 **레벨표와 집계 규칙만** 고친 버전이다"
             "(`screening/rules_v2.py`). 같은 사실, 같은 가중치, 다른 규칙.")
    L.append("")
    L.append("| 지표 | v1 strict | v1 neutral | v2 |")
    L.append("|---|---|---|---|")
    L.append("| 추천 대상 비율 | " + " | ".join(
        f"{mt['modes'][m]['pass_rate']:.0%}" for m in MODES) + " |")
    L.append("| 합격 기업 재현율 | " + " | ".join(
        mt["modes"][m]["admit_recall"] for m in MODES) + " |")
    L.append("| 합격 기업 오탈락 | " + " | ".join(
        f"{len(mt['modes'][m]['admit_rejected'])}개사" for m in MODES) + " |")
    L.append("")
    L.append("수정 내용 4가지:")
    L.append("")
    L.append("1. **스테이지 밴드별 레벨표** — v1 의 절대 레벨표에서는 프리시드가 "
             "Traction L2 상한에 갇혀, 팀·시장·해자가 전부 L5 여도 최대 3.80(B). "
             "밴드별로 '그 단계에서 가능한 최고 속도'를 L5 로 재정의했다.")
    L.append("2. **`확인 필요`를 레벨로 환산 금지** — 증거 등급 `문서 명시` 이상이 "
             "없으면 레벨을 매기지 않는다. v1 은 정보 부재를 L1(strict) 또는 "
             "중간값 L3 로 흡수해, '모르는 것'을 '나쁜 것'으로 바꿨다.")
    L.append(f"3. **커버리지 규칙** — 레벨 확정 축의 가중치 합이 "
             f"{rules_v2.COVERAGE_MIN:.0%} 미만이면 Tier 대신 `판정 보류`. "
             "탈락이 아니라 설문·증빙 요청 상태다.")
    L.append("4. **강등 규칙의 트랙별 분리** — v1 은 어느 축이든 L1 이면 상한 C. "
             "HAX 는 고객 없는 랩 단계에 투자하는 프로그램이므로 고객 축 L1 을 "
             "강등 사유로 쓰면 프로그램 정의와 모순된다. 강등 축을 "
             f"{rules_v2.DEMOTE_AXES} 로 한정했다.")
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


# ---------------------------------------------------------------- 검증 타당성
# v2 규칙은 "어느 합격사가 왜 떨어졌는지" 를 본 뒤에 만들었다. 즉 이 4개사에 대해
# v2 는 in-sample(표본 내) 이다. 어느 판정이 규칙 수정에 의해 구제된 것이고
# 어느 판정이 수정과 무관하게 독립적으로 나온 것인지 구분해 기록한다.
RESCUED_BY = {
    "cardmonster": "수정1 스테이지 밴드별 레벨표 (Traction L2→L3)",
    "stillbright": "수정4 강등 축 트랙별 분리 (고객 L1 강등 면제)",
    "allsale": "수정3 커버리지 규칙 (오탈락 → 보류)",
}


def validity(results: list[dict]) -> dict:
    """이 백테스트로 무엇을 주장할 수 있고 무엇을 주장할 수 없는가."""
    adm = [r for r in results if r["company"].ground_truth.startswith("admitted")]
    rej = [r for r in results if r["company"].ground_truth.startswith("rejected")]
    unk = [r for r in results if r["company"].ground_truth == "unknown"]

    def _rec(g):
        return [r for r in g if "추천 진행" in r["action"]]

    independent = [r["company"].name for r in adm
                   if r["company"].key not in RESCUED_BY
                   and "추천 진행" in r["action"]]
    fp = [r["company"].name for r in rej if "추천 진행" in r["action"]]
    return {
        "n_admitted": len(adm),
        "n_confirmed_rejected": len(rej),
        "n_unknown": len(unk),
        "admit_recommended": f"{len(_rec(adm))}/{len(adm)}",
        "admit_rejected": sum(1 for r in adm if rejected(r, "v2")),
        "control_recommended": f"{len(_rec(unk))}/{len(unk)}",
        # 확정 불합격군에 대한 특이도 — 표본 2개사이므로 지표가 아니라 사례다
        "specificity": f"{len(rej) - len(fp)}/{len(rej)}",
        "false_positives": fp,
        "fp_detail": [
            {"name": r["company"].name,
             "v1": r["scores"]["strict"].tier, "v2": r["scores"]["v2"].tier,
             "fit": r["fit"]}
            for r in rej
        ],
        "separation": (round(len(_rec(adm)) / len(adm), 3),
                       round(len(_rec(unk)) / len(unk), 3)),
        "in_sample": {dataset.by_key(k).name: v for k, v in RESCUED_BY.items()},
        "out_of_sample_pass": independent,
        "measurable": [
            "재현율(합격사를 떨어뜨리지 않는가) — 표본 4개사",
            "합격군 대 대조군 추천율 격차",
            "확정 불합격 2개사에 대한 판정 — 지표가 아니라 사례 수준",
        ],
        "not_measurable": [
            "정밀도·특이도 — 확정 불합격 표본이 2개사뿐(통계적 추정 불가)",
            "일반화 성능 — 합격 표본 4개사, 그중 3개사는 규칙 설계에 사용됨(in-sample)",
            "컷오프 타당성 — 4.00/3.25/2.50 을 검증할 합불 분포가 없음",
            "근접 탈락(지원 후 아깝게 떨어진 기업) — 표본 0건. 정밀도가 실제로 결정되는 구간",
        ],
    }


def render_reevaluation(results: list[dict], mt: dict) -> str:
    """새 평가구조(v2)로 전 기업을 다시 평가한 리포트."""
    d = mt["modes"]["v2"]
    L = ["# 재평가 결과 — 새 평가구조 v2", ""]
    L.append("규칙: `screening/rules_v2.py` / 평가구조 문서: `screening/ENGINE_V2.md`")
    L.append("사실: `screening/dataset.py` (웹 검색 공개 정보만 — 덱·CV·설문 없음)")
    L.append("")
    L.append(f"- 추천 진행/조건부: **{d['pass_rate']:.0%}** · "
             f"판정 보류(설문 요청): {d['n_hold']}개사 · "
             f"실제 합격 기업 오탈락: **{len(d['admit_rejected'])}개사**")
    L.append("")

    v = validity(results)
    L.append("## 0. 이 결과로 무엇을 주장할 수 있는가 (먼저 읽을 것)")
    L.append("")
    L.append(f"- 실제 합격 확인: **{v['n_admitted']}개사** / "
             f"**확정 불합격: {v['n_confirmed_rejected']}개사** / "
             f"합불 미확인 대조군: {v['n_unknown']}개사")
    L.append(f"- 합격군 추천율 **{v['separation'][0]:.0%}** ({v['admit_recommended']}) "
             f"vs 대조군 추천율 **{v['separation'][1]:.0%}** ({v['control_recommended']})")
    L.append(f"- 합격군 오탈락: **{v['admit_rejected']}개사**")
    L.append(f"- 확정 불합격군 정탐: **{v['specificity']}** "
             + (f"— 오탐(탈락 기업을 추천): **{', '.join(v['false_positives'])}**"
                if v["false_positives"] else "— 오탐 없음"))
    L.append("")
    if v["fp_detail"]:
        L.append("### 확정 불합격군 판정 (v1 대 v2)")
        L.append("")
        L.append("| 기업 | v1 strict | v2 | Fit | 판정 |")
        L.append("|---|---|---|---|---|")
        for d in v["fp_detail"]:
            ok = "❌ 오탐" if d["name"] in v["false_positives"] else "✅ 정탐"
            L.append(f"| {d['name']} | {d['v1']} | {d['v2']} | {d['fit']} | {ok} |")
        L.append("")
        L.append("불합격은 원리적으로 공개되지 않는다 — 액셀러레이터는 합격자만 발표하고, "
                 "탈락한 94~97% 는 기록으로 남지 않는다. 위 2건은 **창업자가 스스로 공개한** "
                 "사례로, 검색으로 확보 가능한 전부다.")
        L.append("")
        L.append("**이 표가 말하는 것**: v1 은 SaaSMetrics 를 C 로 올바르게 걸렀고, v2 는 "
                 "B(추천)로 통과시킨다. 재현율을 올린 수정이 정밀도를 깎았다는 직접 증거다. "
                 "특히 Moat 가중치 10% 는 '트랙션은 빠르나 방어자산이 없는' 프로필을 "
                 "막지 못한다 — SaaSMetrics 가 정확히 그 프로필이고, 500 은 실제로 탈락시켰다.")
        L.append("")
    L.append("**측정 가능한 것**")
    for m in v["measurable"]:
        L.append(f"- {m}")
    L.append("")
    L.append("**측정 불가능한 것 — 이 데이터셋으로는 검증되지 않았다**")
    for m in v["not_measurable"]:
        L.append(f"- {m}")
    L.append("")
    L.append("### 표본 내(in-sample) 경고")
    L.append("")
    L.append("v2 규칙은 *어느 합격사가 왜 떨어졌는지 본 뒤에* 만들었다. "
             "따라서 아래 판정은 규칙 수정에 의해 구제된 것이며, "
             "독립 검증이 아니다.")
    L.append("")
    L.append("| 기업 | 어느 수정이 구제했는가 |")
    L.append("|---|---|")
    for name, fix in v["in_sample"].items():
        L.append(f"| {name} | {fix} |")
    L.append("")
    L.append(f"- 수정과 **무관하게** 추천으로 나온 합격사: "
             f"**{', '.join(v['out_of_sample_pass']) or '없음'}** "
             f"({len(v['out_of_sample_pass'])}/{v['n_admitted']})")
    L.append("- 즉 '합격사를 맞춘다'는 주장의 독립적 근거는 현재 "
             f"{len(v['out_of_sample_pass'])}개사뿐이다.")
    L.append("")
    L.append("### 타당성을 확보하려면 (우선순위순)")
    L.append("")
    L.append("1. **확정 불합격 데이터** — 디캠프가 500/HAX 에 추천했거나 500 Korea Seed 에 "
             "지원했다가 탈락한 기업 목록. 이것이 없으면 정밀도·특이도는 영구히 측정 불가다.")
    L.append("2. **합격 표본 확대** — 현재 4개사. HAX 졸업 257개사, 500 포트폴리오 "
             "2,900여 개사가 모집단이므로 확보 가능하다(포트폴리오 페이지 접근 문제 해결 필요).")
    L.append("3. **홀드아웃 분리** — 표본이 20개사 이상 되면 절반으로 규칙을 보정하고 "
             "나머지 절반으로만 검증할 것. 지금은 표본이 작아 불가능하다.")
    L.append("4. **컷오프 재계산** — 1~3 이 확보된 뒤 4.00/3.25/2.50 과 Fit +4/+1 을 "
             "실제 합불 분포로 다시 맞출 것.")
    L.append("")

    L.append("## 조치별 요약")
    L.append("")
    groups: dict[str, list[str]] = {}
    for r in results:
        groups.setdefault(r["action"], []).append(r["company"].name)
    for act, names in sorted(groups.items(), key=lambda x: -len(x[1])):
        L.append(f"- **{act}** ({len(names)}) — {', '.join(names)}")
    L.append("")

    L.append("## 전체 판정표")
    L.append("")
    L.append("| 기업 | 트랙 | 밴드 | 정답 | 게이트 | Tier | Fit(점수) | 조치 |")
    L.append("|---|---|---|---|---|---|---|---|")
    gt = {"admitted_500": "합격(500)", "admitted_hax": "합격(HAX)",
          "rejected_500": "**탈락(500)**", "rejected_multi": "**탈락(복수AC)**",
          "unknown": "미확인", "probe": "게이트 검증"}
    for r in results:
        c = r["company"]
        tier = "라우팅" if r["routed"] else _tier_cell(r, "v2")
        L.append(f"| {c.name} | {c.track} | {c.stage_band} | {gt[c.ground_truth]} | "
                 f"{r['gate']} | {tier} | {r['fit']} ({r['fit_score']:+d}) | "
                 f"{r['action']} |")
    L.append("")

    L.append("## 기업별 상세")
    for r in results:
        c = r["company"]
        L.append(f"\n### {c.name} — {c.sector_note}")
        L.append("")
        L.append(f"- 밴드 **{c.stage_band}** / 트랙 **{c.track}** / 게이트 **{r['gate']}**")
        if r["routed"]:
            L.append("- 바이오 → 점수 미산출, SOSV IndieBio NY/SF 안내")
        else:
            s = r["scores"]["v2"]
            for axis, (lv, why) in dataset.LEVELS_V2.get(c.key, {}).items():
                L.append(f"- **{rules.AXIS_LABELS[axis]}** "
                         f"{'L%d' % lv if lv else '`확인 필요`'} — {why}")
            w = "—" if s.weighted is None else f"{s.weighted:.2f}"
            L.append(f"- 가중평균 **{w}** → **{s.tier}**")
            for n in s.notes:
                L.append(f"  - {n}")
            sig = dataset.FIT.get(c.key, {})
            yes = [k for k, v in sig.items() if v == "yes"]
            no = [k for k, v in sig.items() if v == "no"]
            unk = [k for k, v in sig.items() if v == "unknown"]
            L.append(f"- Fit **{r['fit']}** ({r['fit_score']:+d}) — "
                     f"충족 {len(yes)} / 미충족 {len(no)} / 미확인 {len(unk)}")
            if no:
                L.append("  - 미충족: " + ", ".join(
                    rules_v2.FIT_SIGNALS[k][1] for k in no))
            for n in r["fit_notes"]:
                L.append(f"  - {n}")
        L.append(f"- **조치: {r['action']}**")
        if c.needs_confirm:
            L.append(f"- `확인 필요`: {', '.join(c.needs_confirm)}")
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
        print(f"[{m}] 통과율 {d['pass_rate']:.0%} / 합격기업 재현율 "
              f"{d['admit_recall']} / 합격기업 오탈락 {len(d['admit_rejected'])}개사")
    print(f"[모드 불일치] {len(mt['mode_disagreement'])}개사")

    if a.report:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        body = render_report(results, mt)
        (OUT_DIR / "backtest_report.md").write_text(body, encoding="utf-8")
        (OUT_DIR / "backtest_metrics.json").write_text(
            json.dumps(mt, ensure_ascii=False, indent=2), encoding="utf-8")
        (BASE / "screening" / "RESULTS.md").write_text(body, encoding="utf-8")
        reeval = render_reevaluation(results, mt)
        (OUT_DIR / "reevaluation.md").write_text(reeval, encoding="utf-8")
        (BASE / "screening" / "REEVALUATION.md").write_text(reeval, encoding="utf-8")
        print(f"\n리포트: screening/RESULTS.md (v1↔v2 비교), "
              f"screening/REEVALUATION.md (v2 재평가)")


if __name__ == "__main__":
    main()
