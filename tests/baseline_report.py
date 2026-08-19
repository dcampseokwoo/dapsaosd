"""US FORGED 골든셋 baseline 리포트 (§5).

현재(baseline) 엔진을 골든셋에 돌려 레이어별 통과/실패를 집계하고, 실행에 쓴 스냅샷
provenance 를 기록한다. 결과를 data/snapshots/baseline_golden_report.json 로 고정.

  python -m tests.baseline_report
"""
from __future__ import annotations

import json
from pathlib import Path

from screening import uf_engine, uf_golden, uf_snapshot

ROOT = Path(__file__).resolve().parent.parent


def run() -> dict:
    g = uf_golden.load_golden()
    rows = uf_snapshot.snapshot_rows() if hasattr(uf_snapshot, "snapshot_rows") \
        else uf_golden.snapshot_rows()
    prov = uf_snapshot.provenance(uf_snapshot.DEFAULT_SNAPSHOT,
                                  uf_golden.snapshot_rows())

    res = {"provenance": prov, "layers": {}}

    # 분류 must_pass
    mp_fail = []
    for e in g["classification_must_pass"]:
        v, rec = uf_golden.classification_verdict(e)
        if v != "hardtech":
            mp_fail.append({"name": e["name"], "got": v,
                            "in_snapshot": rec.get("_in_snapshot")})
    res["layers"]["classification_must_pass"] = {
        "total": len(g["classification_must_pass"]),
        "pass": len(g["classification_must_pass"]) - len(mp_fail),
        "fail": len(mp_fail), "broken": mp_fail}

    # 분류 must_fail
    mf_fail = []
    for e in g["classification_must_fail"]:
        v, rec = uf_golden.classification_verdict(e)
        if v == "hardtech":
            mf_fail.append({"name": e["name"], "expect": e.get("expect_verdict"),
                            "in_snapshot": rec.get("_in_snapshot")})
    res["layers"]["classification_must_fail"] = {
        "total": len(g["classification_must_fail"]),
        "pass": len(g["classification_must_fail"]) - len(mf_fail),
        "fail": len(mf_fail), "broken": mf_fail}

    # 스테이지 매핑
    st_fail = []
    for c in g["stage_rules"]["value_mapping"]:
        val, exp = c["value"], c["expect"]
        try:
            got = uf_engine.stage_bucket(val)
            ok = (exp != "RAISE" and got == exp)
        except uf_engine.UnknownStageValue:
            got, ok = "RAISE", (exp == "RAISE")
        if not ok:
            st_fail.append({"value": str(val), "expect": exp, "got": got})
    res["layers"]["stage_value_mapping"] = {
        "total": len(g["stage_rules"]["value_mapping"]),
        "pass": len(g["stage_rules"]["value_mapping"]) - len(st_fail),
        "fail": len(st_fail), "broken": st_fail}

    # malformed biz_no
    mb_fail = []
    for c in g["malformed_biz_no"]:
        _, status = uf_snapshot.normalize_biz_no(c["value"])
        if status not in ("malformed", "valid"):
            mb_fail.append({"name": c["name"], "status": status})
    res["layers"]["malformed_biz_no"] = {
        "total": len(g["malformed_biz_no"]),
        "pass": len(g["malformed_biz_no"]) - len(mb_fail),
        "fail": len(mb_fail), "broken": mb_fail}
    return res


def main():
    r = run()
    p = r["provenance"]
    print("=" * 64)
    print("US FORGED 골든셋 BASELINE (현재 라벨 로직)")
    print("=" * 64)
    print(f"snapshot : {p['input_snapshot']}")
    print(f"sha256   : {p['input_sha256'][:16]}…")
    print(f"rows     : {p['input_rows']}")
    print(f"biz_no   : {p['biz_status_dist']}")
    print(f"stage    : { {k: p['stage_dist'][k] for k in list(p['stage_dist'])[:6]} } …")
    print("-" * 64)
    for name, L in r["layers"].items():
        print(f"[{name}]  {L['pass']}/{L['total']} 통과  (실패 {L['fail']})")
        for b in L["broken"]:
            print(f"    ✗ {b}")
    out = ROOT / "data" / "snapshots" / "baseline_golden_report.json"
    out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print("-" * 64)
    print(f"고정: {out}")


if __name__ == "__main__":
    main()
