"""US FORGED §1 파일럿 집계·리포트.

서브에이전트 분류 결과(pilot_out_*.json)를 모아 (1) 캐시로 고정하고 (2) 골든 정확도,
(3) 표본 40 전건 판정을 보여준다. evidence 가 소개문 실제 인용인지 검증한다.

  python -m tests.pilot_report
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from screening import uf_classify

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"


def _load_items() -> dict:
    items = json.loads((CACHE_DIR / "pilot_items.json").read_text(encoding="utf-8"))
    return {it["idx"]: it for it in items}


def _load_outputs() -> dict:
    by_idx = {}
    for k in range(4):
        p = CACHE_DIR / f"pilot_out_{k}.json"
        if not p.exists():
            raise FileNotFoundError(f"{p.name} 없음 — 에이전트 미완료")
        for o in json.loads(p.read_text(encoding="utf-8")):
            by_idx[o["idx"]] = o
    return by_idx


def build_cache(items: dict, outs: dict) -> int:
    cache = uf_classify.load_cache()
    for idx, it in items.items():
        o = outs.get(idx)
        if not o:
            continue
        rec = {"biz_no": it["biz_no"], "desc": it["desc"]}
        uf_classify.put(rec, {k: o.get(k) for k in
                              ("verdict", "matched_program_field", "physical_product",
                               "evidence", "confidence")}, cache)
    uf_classify.save_cache(cache)
    return len(cache)


def main():
    items, outs = _load_items(), _load_outputs()
    missing = [i for i in items if i not in outs]
    print(f"분류 완료 {len(outs)}/{len(items)}  누락 idx={missing}")

    # evidence 인용 검증
    bad_ev = []
    for idx, it in items.items():
        o = outs.get(idx)
        if not o:
            continue
        ev = (o.get("evidence") or "").strip()
        if ev and ev not in (it["desc"] or ""):
            bad_ev.append((it["name"], ev[:30]))
    print(f"evidence 원문 불일치(창작 의심): {len(bad_ev)}건")
    for n, e in bad_ev[:10]:
        print(f"    ⚠ {n}: {e!r}")

    # 골든 정확도
    g_pass = g_fail = g_pass_ok = g_fail_ok = 0
    g_broken = []
    for idx, it in items.items():
        if it.get("set") != "golden":
            continue
        o = outs.get(idx, {})
        v = o.get("verdict")
        if it["_golden"] == "classification_must_pass":
            g_pass += 1
            if v == "hardtech":
                g_pass_ok += 1
            else:
                g_broken.append((it["name"], "must_pass", v))
        else:
            g_fail += 1
            if v != "hardtech":
                g_fail_ok += 1
            else:
                g_broken.append((it["name"], "must_fail", v))
    print(f"\n[골든] must_pass {g_pass_ok}/{g_pass}  must_fail {g_fail_ok}/{g_fail}")
    for n, layer, v in g_broken:
        print(f"    ✗ {n} ({layer}) → {v}")

    # 표본 40 지표 + 전건
    sample = [(idx, it, outs.get(idx, {})) for idx, it in items.items()
              if it.get("set") == "sample"]
    confs = Counter(o.get("confidence") for _, _, o in sample)
    verds = Counter(o.get("verdict") for _, _, o in sample)
    fields = Counter(o.get("matched_program_field") for _, _, o in sample)
    low = confs.get("low", 0)
    print(f"\n[표본 40] confidence: {dict(confs)}  (low {low}/40 = {100*low//40}%)")
    print(f"          verdict: {dict(verds)}")
    print(f"          matched_field: {dict(fields.most_common())}")

    print("\n[표본 40 전건] (경계유형 | verdict | field | conf | physical | evidence)")
    for idx, it, o in sorted(sample, key=lambda x: (x[1].get("boundary") or "z", x[0])):
        b = (it.get("boundary") or "무작위")[:8]
        print(f"  {b:9} {o.get('verdict','?'):13} {(o.get('matched_program_field') or '')[:22]:22} "
              f"{o.get('confidence','?'):6} phys={str(o.get('physical_product'))[:5]:5} "
              f"| {it['name'][:14]:14} | {(o.get('evidence') or '')[:46]}")

    n = build_cache(items, outs)
    print(f"\n캐시 고정: {uf_classify.CACHE_PATH}  ({n} entries)")


if __name__ == "__main__":
    main()
