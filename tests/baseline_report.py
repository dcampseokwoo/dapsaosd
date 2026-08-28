"""US FORGED 골든셋 baseline 리포트 (§5) — 케이스별(biz_no) 기록.

현재 엔진을 골든셋에 돌려 케이스별 통과/실패를 집계하고 provenance 와 함께
data/snapshots/baseline_golden_report.json 로 고정한다. 래칫 훅이 이 파일을 기준으로
"baseline 보다 나빠지지 않음"을 검사한다.

  python -m tests.baseline_report            # 출력만
  python -m tests.baseline_report --write     # baseline JSON 고정
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from engine import engine_golden, engine_snapshot

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "data" / "snapshots" / "baseline_golden_report.json"


def build() -> dict:
    cases, summary = engine_golden.evaluate_all()
    prov = engine_snapshot.provenance(engine_snapshot.DEFAULT_SNAPSHOT,
                                  engine_golden.snapshot_rows())
    return {"provenance": prov, "summary": summary, "cases": cases}


def main():
    r = build()
    p = r["provenance"]
    print("=" * 64)
    print("US FORGED 골든셋 BASELINE")
    print(f"snapshot {p['input_snapshot']}  sha {p['input_sha256'][:16]}…  "
          f"rows {p['input_rows']}  biz {p['biz_status_dist']}")
    print("-" * 64)
    for layer, s in r["summary"].items():
        print(f"[{layer}]  {s['pass']}/{s['total']}")
    fails = [c for c in r["cases"].values() if not c["pass"]]
    print(f"실패 케이스 {len(fails)}건")
    if "--write" in sys.argv:
        BASELINE_PATH.write_text(json.dumps(r, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print(f"고정: {BASELINE_PATH}")


if __name__ == "__main__":
    main()
