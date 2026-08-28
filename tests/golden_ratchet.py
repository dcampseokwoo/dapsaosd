"""US FORGED 골든셋 래칫 (§5) — pre-commit 회귀 가드.

지난 회귀(무인탐사연구소를 잃고 크레이버를 얻는 식)를 잡기 위해, "전부 통과"가 아니라
**"baseline 보다 나빠지지 않음"**을 검사한다:

  ① 통과 수가 baseline 이상
  ② baseline 에서 통과하던 케이스가 새로 실패하지 않음   ← 핵심(개수 상쇄 방지)

개선되면 `--update-baseline` 으로 baseline 을 갱신한다. 마지막에 기준을 "전부 통과"로
올리려면 baseline 을 전건 통과 상태로 갱신하면 된다.

  python -m tests.golden_ratchet                 # 검사(회귀 시 exit 1)
  python -m tests.golden_ratchet --update-baseline
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from engine import engine_golden

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "data" / "snapshots" / "baseline_golden_report.json"


def _load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        return {"cases": {}, "summary": {}}
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def check() -> int:
    base = _load_baseline()
    cases, summary = engine_golden.evaluate_all()
    base_cases = base.get("cases", {})

    # ② baseline 에서 통과하던 케이스가 이제 실패 → 회귀
    regressions = []
    for cid, bc in base_cases.items():
        if bc.get("pass") and cid in cases and not cases[cid]["pass"]:
            regressions.append((cid, cases[cid]))

    # ① 통과 수 baseline 이상 (레이어별)
    shortfalls = []
    base_sum = base.get("summary", {})
    for layer, s in summary.items():
        bp = base_sum.get(layer, {}).get("pass", 0)
        if s["pass"] < bp:
            shortfalls.append((layer, s["pass"], bp))

    now = sum(s["pass"] for s in summary.values())
    was = sum(s.get("pass", 0) for s in base_sum.values())
    print(f"골든셋 래칫: 통과 {now} (baseline {was})")

    if not regressions and not shortfalls:
        if now > was:
            print(f"  개선됨(+{now - was}). 반영하려면 --update-baseline")
        else:
            print("  회귀 없음 ✓")
        return 0

    print("  🔴 회귀 감지 — 커밋 차단")
    for cid, c in regressions:
        print(f"    [신규 실패] {cid}  ({c['label']}) got={c['got']}")
    for layer, cur, bp in shortfalls:
        print(f"    [통과 감소] {layer}: {cur} < baseline {bp}")
    return 1


def update() -> int:
    from tests.baseline_report import build
    r = build()
    BASELINE_PATH.write_text(json.dumps(r, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    passed = sum(s["pass"] for s in r["summary"].values())
    total = sum(s["total"] for s in r["summary"].values())
    print(f"baseline 갱신: {passed}/{total} 통과 → {BASELINE_PATH.name}")
    return 0


def main() -> int:
    if "--update-baseline" in sys.argv:
        return update()
    return check()


if __name__ == "__main__":
    sys.exit(main())
