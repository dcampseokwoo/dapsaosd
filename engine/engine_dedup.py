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

from engine import engine_stage


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


def is_one_digit_diff(a: str, b: str) -> bool:
    """두 사업자번호가 정확히 1자리만 다름(오타 강의심 → 병합). 예: 661↔667, 367↔364."""
    da, db = _digits(a), _digits(b)
    if len(da) != 10 or len(db) != 10 or da == db:
        return False
    return sum(1 for x, y in zip(da, db) if x != y) == 1


def _norm_name(name: str) -> str:
    """법인격·공백 제거한 정규화 사명(그룹핑 키). '주식회사 워커린스페이스'='워커린스페이스'."""
    return re.sub(r"주식회사|\(주\)|㈜|㈔|\(유\)|유한회사|\s", "", name or "")


def _load_manual_merges() -> list[dict]:
    """수동 병합 목록(1자리차로 못 잡는 확인된 동일 회사). global + 활성 기준팩 병합."""
    from pathlib import Path
    import yaml
    from engine import criteria_pack
    g = Path(__file__).resolve().parent.parent / "config" / "global_exclusions.yaml"
    merges = []
    if g.exists():
        merges += (yaml.safe_load(g.read_text(encoding="utf-8")) or {}).get("duplicate_merges", []) or []
    merges += criteria_pack.exclusions().get("duplicate_merges", []) or []
    return merges


_MANUAL_MERGE_SETS = None


def _manual_merge_of(biz: str) -> frozenset | None:
    global _MANUAL_MERGE_SETS
    if _MANUAL_MERGE_SETS is None:
        _MANUAL_MERGE_SETS = [frozenset(m.get("biz_nos", [])) for m in _load_manual_merges()]
    for s in _MANUAL_MERGE_SETS:
        if biz in s:
            return s
    return None


def _merge_same_biz(rows: list[dict]) -> dict:
    """같은 사업자번호 여러 행 → 보수적 병합. 스테이지 충돌 시 후기, 업종/소개는 합집합."""
    best = max(rows, key=lambda r: engine_stage.stage_rank(r.get("stage")))
    ent = dict(best)
    inds = [r.get("industry", "") for r in rows if r.get("industry")]
    ent["industry"] = " ; ".join(dict.fromkeys(inds))
    ent["merged_from"] = sorted({r.get("biz_no", "") for r in rows})
    ent["merge_note"] = f"{len(rows)}행 동일 사업자번호 보수적 병합(후기 스테이지 채택)"
    return ent


def _cluster(uids: list[str]) -> list[list[str]]:
    """식별 uid 들을 병합 클러스터로 묶는다: 동일 uid(기본) + 1자리차 + 수동병합 목록."""
    parent = {u: u for u in uids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    for i, a in enumerate(uids):
        ma = _manual_merge_of(a)
        for b in uids[i + 1:]:
            if is_one_digit_diff(a, b) or (ma and b in ma):
                union(a, b)
    groups: dict[str, list[str]] = defaultdict(list)
    for u in uids:
        groups[find(u)].append(u)
    return list(groups.values())


def resolve_entities(rows: list[dict]) -> list[dict]:
    """행 리스트 → 신원 판정된 엔티티 리스트. 각 엔티티에 identity/flags/merged_from.

    정규화 사명으로 그룹핑(표기 차 흡수) → 식별 행을 클러스터(동일 사업자번호 / 1자리차 오타
    / 수동병합 목록)로 묶어 병합. 1자리 초과 근접(오믈렛류)은 병합 않고 suspect 플래그만.
    """
    by_name: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_name[_norm_name(r["name_ko"])].append(r)

    entities = []
    for _nm, group in by_name.items():
        identified = [r for r in group
                      if r["biz_status"] == "valid"
                      or (r["biz_status"] == "foreign" and r["uid"] == r["biz_no"])]
        unident = [r for r in group if r not in identified]
        by_uid: dict[str, list[dict]] = defaultdict(list)
        for r in identified:
            by_uid[r["uid"]].append(r)
        uids = list(by_uid)
        clusters = _cluster(uids)          # 병합 후 클러스터(각각 1개 엔티티)

        # 1자리 초과 근접(병합 안 됨) → suspect 플래그
        sim_bizes = set()
        for i, a in enumerate(uids):
            for b in uids[i + 1:]:
                if is_similar_biz(a, b) and not is_one_digit_diff(a, b):
                    sim_bizes.update({a, b})

        multi = len(clusters) >= 2
        for cl in clusters:
            rws = [r for u in cl for r in by_uid[u]]
            ent = _merge_same_biz(rws) if len(rws) > 1 else dict(rws[0])
            ent["identity"] = "name_collision" if multi else "canonical_valid"
            ent["flags"] = ["name_collision"] if multi else []
            if any(u in sim_bizes for u in cl):
                ent["flags"].append("similar_biz_no_suspect")
            ent.setdefault("merged_from",
                           sorted({r["biz_no"] for r in rws}) if len(rws) > 1 else [])
            # 유효 하나뿐(단일 클러스터)일 때만 결측 행을 참고로 첨부
            if not multi and unident:
                ent["flags"].append("has_reference_rows")
                ent["reference_rows"] = [{"stage": r.get("stage"),
                                          "biz_status": r["biz_status"]} for r in unident]
            entities.append(ent)

        if not clusters:               # 유효 사업자번호 없음
            for r in unident:
                e = dict(r); e["identity"] = "needs_review"; e["flags"] = ["no_valid_biz_no"]
                entities.append(e)
        elif multi:                    # name_collision 그룹의 귀속 불가 결측 행
            for r in unident:
                e = dict(r); e["identity"] = "needs_review"
                e["flags"] = ["name_collision", "unattributable"]
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
