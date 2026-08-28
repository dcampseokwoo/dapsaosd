"""US FORGED — §1 전체 분류 집계 + 3회 다수결 + 캐시 고정 (결정적, API 불필요).

파이프라인:
  1) pass1: 서브에이전트가 full_items.json 전건 분류 → data/cache/full_out_p1_*.json
  2) aggregate_pass1(): 병합·검증 → biz_no별 verdict
  3) recheck_subset(): 소개문에 상충 신호가 있어 흔들리기 쉬운 건만 추림
     (confidence!=high OR verdict==unclear OR consumer_facing OR maturity_signal)
  4) pass2/pass3: 그 서브셋만 2회 추가 분류 → full_out_p2_*.json, full_out_p3_*.json
  5) finalize(): 다수결(3회) → 캐시 저장. 3회가 다 갈리면 disagreement=true. 3회 이력 보관.

이 모듈은 파일만 다룬다(분류 자체는 서브에이전트가 한 것). 한도 복구 후 재개용.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from engine import engine_classify

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
_FIELDS = ("verdict", "matched_program_field", "physical_product",
           "consumer_facing_end_product", "maturity_signal", "evidence", "confidence")


def _read_outputs(glob_pat: str) -> dict:
    """full_out_<pat>_*.json 병합 → idx→object."""
    by_idx = {}
    for p in sorted(CACHE_DIR.glob(glob_pat)):
        for o in json.loads(p.read_text(encoding="utf-8")):
            by_idx[o["idx"]] = o
    return by_idx


def _items() -> list[dict]:
    return json.loads((CACHE_DIR / "full_items.json").read_text(encoding="utf-8"))


def aggregate_pass1() -> dict:
    items = _items()
    outs = _read_outputs("full_out_p1_*.json")
    missing = [it["idx"] for it in items if it["idx"] not in outs]
    return {"items": items, "pass1": outs, "missing": missing,
            "n": len(items), "done": len(outs)}


def is_unstable(o: dict) -> bool:
    """소개문 상충 신호 → 재검 대상(3회 다수결).

    medium confidence 는 불안정과 무관(파일럿 92% 일관성은 confidence 무관하게 유지)이라
    제외하고, 진짜 흔들리는 신호만 잡는다: low confidence · unclear · 하드테크인데 소비자용
    (수직계열화 vs 완제품 경계) · maturity_signal(기성 제조 경계).
    """
    return (o.get("confidence") == "low" or o.get("verdict") == "unclear"
            or (o.get("verdict") == "hardtech" and o.get("consumer_facing_end_product"))
            or bool((o.get("maturity_signal") or "").strip()))


def recheck_subset() -> list[dict]:
    """pass1 결과 중 불안정 건의 items(재분류 입력용)."""
    agg = aggregate_pass1()
    idx_items = {it["idx"]: it for it in agg["items"]}
    subset = [idx_items[i] for i, o in agg["pass1"].items() if is_unstable(o)]
    # 재분류용 idx 재부여
    for j, it in enumerate(subset):
        it = dict(it); it["_orig_idx"] = it["idx"]; it["ridx"] = j
    return [{**it, "ridx": j} for j, it in enumerate(subset)]


def _majority(verdicts: list[str]) -> tuple[str, bool]:
    """다수결 verdict + disagreement(3표가 다 다르면 True)."""
    c = Counter(verdicts)
    top, n = c.most_common(1)[0]
    disagreement = len(c) == len(verdicts) and len(verdicts) >= 3
    return top, disagreement


def finalize() -> dict:
    """pass1 + (있으면)pass2/pass3 다수결 → 캐시 저장. 반환: 통계."""
    items = _items()
    idx2biz = {it["idx"]: it["biz_no"] for it in items}
    biz2desc = {it["biz_no"]: it["desc"] for it in items}
    p1 = _read_outputs("full_out_p1_*.json")

    # 재검(p2/p3)은 ridx 기반으로 매핑(사업자번호 placeholder 충돌 방지, §4 버그).
    recheck = json.loads((CACHE_DIR / "recheck_items.json").read_text(encoding="utf-8"))
    key2ridx = {(it["biz_no"], it["desc"]): it["idx"] for it in recheck}

    def by_ridx(pat):
        d = {}
        for p in sorted(CACHE_DIR.glob(pat)):
            for o in json.loads(p.read_text(encoding="utf-8")):
                d[o["idx"]] = o
        return d
    p2, p3 = by_ridx("full_out_p2_*.json"), by_ridx("full_out_p3_*.json")

    cache = engine_classify.load_cache()
    stats = Counter()
    disagreements = []
    for idx, biz in idx2biz.items():
        o1 = p1.get(idx)
        if not o1:
            continue
        passes = [o1]
        ridx = key2ridx.get((biz, biz2desc.get(biz, "")))
        if ridx is not None:
            if ridx in p2:
                passes.append(p2[ridx])
            if ridx in p3:
                passes.append(p3[ridx])
        if len(passes) >= 3:
            verdict, dis = _majority([p["verdict"] for p in passes])
            chosen = next(p for p in passes if p["verdict"] == verdict)
        else:
            verdict, dis, chosen = o1["verdict"], False, o1
        entry = {k: chosen.get(k) for k in _FIELDS}
        entry["verdict"] = verdict
        entry["disagreement"] = dis
        entry["history"] = [{"verdict": p["verdict"], "confidence": p.get("confidence")}
                            for p in passes]
        engine_classify.put({"biz_no": biz, "desc": biz2desc.get(biz, "")}, entry, cache)
        stats[verdict] += 1
        if dis:
            disagreements.append({"biz_no": biz,
                                  "verdicts": [p["verdict"] for p in passes]})
    engine_classify.save_cache(cache)
    return {"verdict_dist": dict(stats.most_common()),
            "disagreements": disagreements, "n_cached": sum(stats.values())}
