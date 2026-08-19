"""US FORGED 골든셋 하네스 지원 — 로더·레이어 헬퍼 (pytest 와 baseline 리포트 공용).

골든셋(tests/golden_set.yaml)과 고정 스냅샷을 로드하고, 기업을 **사업자번호로** 찾아
엔진 레이어(배제→스테이지→분류)를 호출하는 얇은 헬퍼. 골든셋 설계 원칙:
  - 기업 식별은 biz_no (사명 변경·중복에 강함)
  - classification_* 는 스테이지 무관
  - stage_rules 는 값→버킷 매핑만
"""
from __future__ import annotations

from pathlib import Path

import yaml

from screening import uf_engine, uf_snapshot

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_PATH = ROOT / "tests" / "golden_set.yaml"


def load_golden() -> dict:
    return yaml.safe_load(GOLDEN_PATH.read_text(encoding="utf-8"))


_ROWS = None
_IDX = None


def snapshot_rows() -> list[dict]:
    global _ROWS
    if _ROWS is None:
        _ROWS = uf_snapshot.load_rows()
    return _ROWS


def snapshot_index() -> dict[str, list[dict]]:
    global _IDX
    if _IDX is None:
        _IDX = uf_snapshot.index_by_biz(snapshot_rows())
    return _IDX


def rec_for(entry: dict) -> dict:
    """골든셋 항목 → 분류 입력 rec. 스냅샷에 있으면 실제 소개문 사용, 없으면 골든셋 값.

    반환에 `_in_snapshot` 로 출처를 표시한다(스냅샷 비의존 검증을 위해).
    """
    biz, _ = uf_snapshot.normalize_biz_no(entry.get("biz_no"))
    hits = snapshot_index().get(biz, [])
    if hits:
        r = dict(hits[0])
        r["_in_snapshot"] = True
        return r
    # 스냅샷에 없음 → 골든셋 필드로 최소 rec 구성
    return {"_in_snapshot": False, "biz_no": biz,
            "name_ko": entry.get("name", ""), "name_en": entry.get("name", ""),
            "industry": entry.get("db_industry", ""), "tech": "",
            "desc": entry.get("reason", ""), "svc": "", "stage": "", "target": ""}


def classification_verdict(entry: dict) -> tuple[str, dict]:
    """골든셋 항목의 하드테크 판정(배제+분류, 스테이지 무관) → (verdict, rec)."""
    rec = rec_for(entry)
    return uf_engine.hardtech_verdict(rec), rec


def _case_id(layer: str, key) -> str:
    return f"{layer}:{key}"


def evaluate_all() -> tuple[dict, dict]:
    """골든셋 전 케이스를 현재 엔진으로 평가 → (cases, summary).

    cases[case_id] = {layer, label, pass, got, expect}. 식별자는 biz_no(분류)/값(스테이지)/
    사명(malformed). 래칫 훅·baseline 리포트·pytest 가 이 함수를 공유한다.
    """
    g = load_golden()
    cases: dict[str, dict] = {}

    for e in g["classification_must_pass"]:
        biz, _ = uf_snapshot.normalize_biz_no(e.get("biz_no"))
        v, _rec = classification_verdict(e)
        cid = _case_id("must_pass", biz or e["name"])
        cases[cid] = {"layer": "classification_must_pass", "label": e["name"],
                      "pass": v == "hardtech", "got": v, "expect": "hardtech"}

    for e in g["classification_must_fail"]:
        biz, _ = uf_snapshot.normalize_biz_no(e.get("biz_no"))
        v, _rec = classification_verdict(e)
        cid = _case_id("must_fail", biz or e["name"])
        cases[cid] = {"layer": "classification_must_fail", "label": e["name"],
                      "pass": v != "hardtech", "got": v,
                      "expect": e.get("expect_verdict", "non-hardtech")}

    for c in g["stage_rules"]["value_mapping"]:
        val, exp = c["value"], c["expect"]
        try:
            got = uf_engine.stage_bucket(val)
            ok = (exp != "RAISE" and got == exp)
        except uf_engine.UnknownStageValue:
            got, ok = "RAISE", (exp == "RAISE")
        cases[_case_id("stage", str(val))] = {
            "layer": "stage_value_mapping", "label": str(val),
            "pass": ok, "got": got, "expect": exp}

    for c in g["malformed_biz_no"]:
        _, status = uf_snapshot.normalize_biz_no(c["value"])
        ok = status in ("malformed", "valid")
        if "725-870" in c["value"]:
            ok = status == "malformed"
        cases[_case_id("malformed", c["name"])] = {
            "layer": "malformed_biz_no", "label": c["name"],
            "pass": ok, "got": status, "expect": "malformed/valid"}

    # 중복 엔티티 (§2 신원 판정) + Pre-A 예외 (§3)
    from screening import uf_dedup, uf_stage
    ents = uf_dedup.resolve_entities(snapshot_rows())
    ent_by_biz: dict[str, dict] = {}
    for e in ents:
        if e.get("biz_no"):
            ent_by_biz.setdefault(e["biz_no"], e)

    def _disposition(e: dict) -> str:
        b = uf_stage.stage_bucket(e.get("stage"))
        if b in (uf_stage.IN_SCOPE, uf_stage.UNKNOWN):
            return "to_classification"
        if b == uf_stage.OUT_OF_SCOPE:
            return "excluded"
        # EXCEPTION(Pre-A): 미국+physical(=§1) 이면 통과, 아니면 배제. physical 은 §3 단계라 True 가정.
        return ("to_classification"
                if uf_stage.pre_a_bucket(e.get("target", ""), True) == "stage_exception"
                else "excluded")

    for d in g["duplicate_entities"]:
        nm, exp = d["name"], d["expect"]
        if exp == "canonical_valid":
            biz = d["canonical_biz_no"]
            e = ent_by_biz.get(biz)
            ok = bool(e) and e["identity"] == "canonical_valid" \
                and e.get("stage") == d.get("canonical_stage")
            cases[_case_id("dup", biz)] = {
                "layer": "duplicate_entities", "label": f"{nm}(정본)",
                "pass": ok, "got": e and (e["identity"], e.get("stage")),
                "expect": ("canonical_valid", d.get("canonical_stage"))}
        else:  # name_collision (+ suspect)
            for spec in d.get("entities", []):
                biz = spec["biz_no"]
                e = ent_by_biz.get(biz)
                ok = bool(e) and e["identity"] == "name_collision"
                if e and "expect_final" in spec:
                    ok = ok and _disposition(e) == spec["expect_final"]
                if d.get("suspect") == "similar_biz_no" and e:
                    ok = ok and "similar_biz_no_suspect" in e.get("flags", [])
                cases[_case_id("dup", biz)] = {
                    "layer": "duplicate_entities", "label": f"{nm}/{biz}",
                    "pass": ok, "got": e and (e["identity"], _disposition(e)),
                    "expect": (exp, spec.get("expect_final"))}

    for pa in g["stage_rules"].get("pre_a_exception", []):
        biz = pa["biz_no"]
        e = ent_by_biz.get(biz)
        if not e:
            got = "not_found"
        else:
            b = uf_stage.stage_bucket(e.get("stage"))
            got = (uf_stage.pre_a_bucket(e.get("target", ""), True) if b == uf_stage.EXCEPTION
                   else ("OUT_OF_SCOPE" if b == uf_stage.OUT_OF_SCOPE else b))
        exp = pa["expect_bucket"]
        ok = (got == exp) or (exp == "stage_exception_or_out_of_scope"
                              and got in ("stage_exception", "OUT_OF_SCOPE"))
        cases[_case_id("pre_a", biz)] = {
            "layer": "pre_a_exception", "label": pa["name"],
            "pass": ok, "got": got, "expect": exp}

    summary: dict[str, dict] = {}
    for c in cases.values():
        s = summary.setdefault(c["layer"], {"pass": 0, "total": 0})
        s["total"] += 1
        s["pass"] += 1 if c["pass"] else 0
    return cases, summary
