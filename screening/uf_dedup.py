"""US FORGED — 중복/신원 정규화 (§2).

**병합 전에 신원부터 판정한다.** 무조건 '후기 스테이지 채택'을 적용하면 식별자 없는
행이 정상 행을 밀어내는 데이터 품질 역전이 생긴다(딥메트릭스). 업종이 크게 다른데
사명만 같은 건 동명이인일 수 있어 병합하면 존재하지 않는 회사를 만든다(알피).

신원 판정 순서:
  1) 유효 사업자번호가 둘 이상 서로 다름 → 별개 엔티티(name_collision). 병합 금지.
  2) 유효가 하나뿐 → 그 행이 정본(canonical). 결측 행은 참고만, 정본을 덮어쓰지 않음.
  3) 같은 사업자번호가 여러 행 → 진짜 중복. 여기서만 보수적 병합(스테이지 충돌 시 후기).
자릿수 전치 의심(563-88-23981 vs 563-88-02981)은 자동 병합하지 않고 플래그+리포트.
"""
from __future__ import annotations

import re
from collections import defaultdict

from screening import uf_stage


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def is_transposition(a: str, b: str) -> bool:
    """두 사업자번호가 같은 숫자 집합인데 순서만 다름(순수 전치)."""
    da, db = _digits(a), _digits(b)
    return len(da) == 10 and da != db and sorted(da) == sorted(db)


def is_similar_biz(a: str, b: str) -> bool:
    """근접 유사 사업자번호 의심 — 전치 또는 소수 자리 치환(≤2). 사람 검토용 플래그.

    예: 563-88-23981 vs 563-88-02981 은 전치가 아니라 2자리 치환이지만 오입력 의심이다.
    """
    da, db = _digits(a), _digits(b)
    if len(da) != 10 or len(db) != 10 or da == db:
        return False
    if sorted(da) == sorted(db):
        return True
    return sum(1 for x, y in zip(da, db) if x != y) <= 2


def _merge_same_biz(rows: list[dict]) -> dict:
    """같은 사업자번호 여러 행 → 보수적 병합. 스테이지 충돌 시 후기, 업종/소개는 합집합."""
    best = max(rows, key=lambda r: uf_stage.stage_rank(r.get("stage")))
    ent = dict(best)
    inds = [r.get("industry", "") for r in rows if r.get("industry")]
    ent["industry"] = " ; ".join(dict.fromkeys(inds))
    ent["merged_from"] = sorted({r.get("biz_no", "") for r in rows})
    ent["merge_note"] = f"{len(rows)}행 동일 사업자번호 보수적 병합(후기 스테이지 채택)"
    return ent


def resolve_entities(rows: list[dict]) -> list[dict]:
    """행 리스트 → 신원 판정된 엔티티 리스트. 각 엔티티에 identity/flags/merged_from."""
    by_name: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_name[r["name_ko"]].append(r)

    entities = []
    for name, group in by_name.items():
        # placeholder/비고유 foreign 은 uid 가 복합키라 자동으로 분리됨(§4 식별 버그 방지)
        identified = [r for r in group
                      if r["biz_status"] == "valid"
                      or (r["biz_status"] == "foreign" and r["uid"] == r["biz_no"])]
        unident = [r for r in group if r not in identified]
        by_biz: dict[str, list[dict]] = defaultdict(list)
        for r in identified:
            by_biz[r["uid"]].append(r)
        distinct = list(by_biz)

        if len(distinct) >= 2:
            # 1) name_collision — 병합 금지, 각 사업자번호가 별개 엔티티
            sim_pairs = [(a, b) for i, a in enumerate(distinct)
                         for b in distinct[i + 1:] if is_similar_biz(a, b)]
            sim_bizes = {x for pair in sim_pairs for x in pair}
            for biz, rws in by_biz.items():
                ent = _merge_same_biz(rws) if len(rws) > 1 else dict(rws[0])
                ent["identity"] = "name_collision"
                ent["flags"] = ["name_collision"]
                if biz in sim_bizes:
                    ent["flags"].append("similar_biz_no_suspect")
                ent.setdefault("merged_from", sorted({r["biz_no"] for r in rws}) if len(rws) > 1 else [])
                entities.append(ent)
            for r in unident:   # 귀속 불가한 결측 행
                e = dict(r); e["identity"] = "needs_review"
                e["flags"] = ["name_collision", "unattributable"]
                entities.append(e)

        elif len(distinct) == 1:
            # 2) 유효 하나 → 정본. 결측 행은 참고만(정본 안 덮음)
            biz = distinct[0]
            rws = by_biz[biz]
            ent = _merge_same_biz(rws) if len(rws) > 1 else dict(rws[0])
            ent["identity"] = "canonical_valid"
            ent["flags"] = []
            ent.setdefault("merged_from", sorted({r["biz_no"] for r in rws}) if len(rws) > 1 else [])
            if unident:
                ent["flags"].append("has_reference_rows")
                ent["reference_rows"] = [{"stage": r.get("stage"),
                                          "biz_status": r["biz_status"]} for r in unident]
            entities.append(ent)

        else:
            # 3) 유효 사업자번호 없음 → 전부 결측/오류. 사람 검토
            for r in unident:
                e = dict(r); e["identity"] = "needs_review"; e["flags"] = ["no_valid_biz_no"]
                entities.append(e)

    return entities


def duplicate_report(rows: list[dict]) -> list[dict]:
    """사명이 2행 이상인 그룹의 신원 판정 결과(중복 시트/사람 확인용)."""
    by_name: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_name[r["name_ko"]].append(r)
    ents_by_name: dict[str, list[dict]] = defaultdict(list)
    for e in resolve_entities(rows):
        ents_by_name[e["name_ko"]].append(e)

    report = []
    for name, group in by_name.items():
        if len(group) < 2:
            continue
        ents = ents_by_name[name]
        idents = sorted({e["identity"] for e in ents})
        flags = sorted({f for e in ents for f in e.get("flags", [])})
        report.append({
            "name": name, "rows": len(group), "entities": len(ents),
            "identity": ",".join(idents), "flags": ",".join(flags),
            "biz_nos": [r["biz_no_raw"] or "(결측)" for r in group],
            "stages": [r.get("stage") for r in group],
        })
    report.sort(key=lambda x: (-x["rows"], x["name"]))
    return report
