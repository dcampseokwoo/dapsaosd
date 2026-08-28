"""US FORGED — 스냅샷 diff 모드 (§7).

살아있는 시트에서 export될 때마다 값이 바뀌므로(18시간 만에 스테이지 652곳 변동),
두 스냅샷을 받아 (1) 어떤 기업의 어떤 컬럼이 바뀌었는지, (2) 그 변경이 후보 리스트에
미치는 영향(신규 진입/이탈)을 낸다.

구현 상태(§7 지시대로):
  - (1) 컬럼 단위 diff: **구현**. 기업 식별은 정규화 사업자번호.
  - (2) 후보 영향: **인터페이스만**. 최종 파이프라인(§1~4)이 아직 없어 shortlist 함수를
        주입받는 형태로 열어두고, 미주입 시 명확히 보류를 알린다.

  python -m engine.engine_diff <old.xlsx> <new.xlsx>
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from engine import engine_snapshot

# 변동을 주로 추적할 컬럼(전 컬럼 비교하되 요약은 이 순서로)
TRACK_COLS = ["stage", "industry", "target", "name_ko", "name_en", "desc",
              "foundation_type", "investor"]


def _index_first(rows: list[dict]) -> dict[str, dict]:
    """정규화 사업자번호 → 첫 행(중복은 §2 병합 소관이라 여기선 첫 행)."""
    idx: dict[str, dict] = {}
    for r in rows:
        if r["biz_no"] and r["biz_no"] not in idx:
            idx[r["biz_no"]] = r
    return idx


def column_diff(old_rows: list[dict], new_rows: list[dict]) -> dict:
    """두 스냅샷의 컬럼 단위 변경. 반환: changed/added/removed + 스테이지 전이 요약."""
    old_i, new_i = _index_first(old_rows), _index_first(new_rows)
    old_k, new_k = set(old_i), set(new_i)

    changed = {}
    stage_transitions = Counter()
    for biz in old_k & new_k:
        o, n = old_i[biz], new_i[biz]
        cols = {}
        for c in TRACK_COLS:
            if (o.get(c) or "") != (n.get(c) or ""):
                cols[c] = [o.get(c, ""), n.get(c, "")]
        if cols:
            changed[biz] = {"name": n.get("name_ko", ""), "cols": cols}
        if "stage" in cols:
            stage_transitions[f"{cols['stage'][0] or '∅'} → {cols['stage'][1] or '∅'}"] += 1

    return {
        "added": [{"biz_no": b, "name": new_i[b]["name_ko"]} for b in sorted(new_k - old_k)],
        "removed": [{"biz_no": b, "name": old_i[b]["name_ko"]} for b in sorted(old_k - new_k)],
        "changed": changed,
        "stage_transitions": dict(stage_transitions.most_common()),
        "summary": {"added": len(new_k - old_k), "removed": len(old_k - new_k),
                    "changed": len(changed)},
    }


def candidate_impact(old_rows: list[dict], new_rows: list[dict], shortlist_fn=None) -> dict:
    """스냅샷 변경이 후보 리스트(shortlist)에 미치는 영향 — 신규 진입/이탈.

    shortlist_fn(rows) -> set[biz_no] 를 주입하면 두 스냅샷의 shortlist 집합을 비교한다.
    최종 파이프라인(§1~4)이 완성되면 uf_pipeline.shortlist 를 넘겨 활성화한다.
    미주입 시 NotImplementedError 로 보류를 명시(조용히 빈 결과 내지 않음).
    """
    if shortlist_fn is None:
        raise NotImplementedError(
            "candidate_impact: shortlist_fn 미주입 — 최종 파이프라인(§1~4) 완성 후 "
            "uf_pipeline.shortlist 를 주입해 활성화한다. 지금은 column_diff 만 사용.")
    old_sl, new_sl = shortlist_fn(old_rows), shortlist_fn(new_rows)
    return {"entered": sorted(new_sl - old_sl), "left": sorted(old_sl - new_sl),
            "stayed": len(old_sl & new_sl)}


def run_diff(old_path, new_path, shortlist_fn=None) -> dict:
    old_rows = engine_snapshot.load_rows(old_path)
    new_rows = engine_snapshot.load_rows(new_path)
    out = {
        "old": engine_snapshot.provenance(old_path, old_rows),
        "new": engine_snapshot.provenance(new_path, new_rows),
        "column_diff": column_diff(old_rows, new_rows),
    }
    try:
        out["candidate_impact"] = candidate_impact(old_rows, new_rows, shortlist_fn)
    except NotImplementedError as e:
        out["candidate_impact"] = {"deferred": str(e)}
    return out


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print("usage: python -m engine.engine_diff <old.xlsx> <new.xlsx>")
        return 2
    d = run_diff(Path(argv[0]), Path(argv[1]))
    s = d["column_diff"]["summary"]
    print(f"old {d['old']['input_snapshot']} ({d['old']['input_rows']}행) → "
          f"new {d['new']['input_snapshot']} ({d['new']['input_rows']}행)")
    print(f"신규 {s['added']} / 이탈 {s['removed']} / 변경 {s['changed']}")
    print("스테이지 전이 top:")
    for k, n in list(d["column_diff"]["stage_transitions"].items())[:10]:
        print(f"  {n:4}  {k}")
    ci = d["candidate_impact"]
    print("후보 영향:", ci.get("deferred", ci))
    return 0


if __name__ == "__main__":
    sys.exit(main())
