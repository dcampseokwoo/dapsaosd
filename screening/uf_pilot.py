"""US FORGED — §1 분류 파일럿 표본 구성.

파일럿 = 골든 36 + 무작위 40(시드 고정). 표본은 스테이지 통과 풀(1,159)에서 뽑되,
감사에서 판단 유보됐던 경계 5유형이 반드시 포함되도록 층화한다:
  1 파운드리·수탁제조  2 소재 상사·무역  3 연구용역·엔지니어링 컨설팅
  4 하드웨어+SaaS(통과가 맞는 유형)  5 기성 부품 제조 중소기업(스타트업 아님 의심)
"""
from __future__ import annotations

import random
import re

from screening import uf_dedup, uf_snapshot, uf_stage

BOUNDARY = {
    "1_수탁제조": re.compile(r"파운드리|foundry|수탁|위탁\s*생산|위탁\s*제조|OEM|ODM|임가공|주문\s*제작", re.I),
    "2_상사무역": re.compile(r"상사|무역|trading|유통|도매|수입\s*판매|디스트리뷰|distributor", re.I),
    "3_용역컨설팅": re.compile(r"용역|엔지니어링\s*컨설팅|컨설팅|consulting|시험\s*인증|시험\s*분석|"
                          r"자문|개발\s*대행|설계\s*대행|R&D\s*대행", re.I),
    "4_하드+SaaS": re.compile(r"(센서|디바이스|웨어러블|하드웨어|장비|기기|모듈|계측|측정|로봇)"
                           r"(.{0,60})(구독|saas|데이터|플랫폼|platform|모니터링|monitoring|분석\s*서비스|클라우드)", re.I),
    "5_기성제조": re.compile(r"(공업|금속|철강|중공업|정밀|주물|단조|부품|기계).{0,20}(제조|생산|가공)|"
                          r"(공업|금속|철강|중공업|정밀|산업)\s*$"),
}


def stage_pool(rows=None) -> list[dict]:
    """스테이지 필터 통과 엔티티(IN_SCOPE/UNKNOWN/Pre-A·미국 예외후보)."""
    rows = rows if rows is not None else uf_snapshot.load_rows()
    pool = []
    for e in uf_dedup.resolve_entities(rows):
        b = uf_stage.stage_bucket(e.get("stage"))
        if b in (uf_stage.IN_SCOPE, uf_stage.UNKNOWN):
            e = dict(e); e["_stage_bucket"] = b; pool.append(e)
        elif b == uf_stage.EXCEPTION and "미국" in (e.get("target") or ""):
            e = dict(e); e["_stage_bucket"] = "PRE_A_PROVISIONAL"; pool.append(e)
    return pool


def _match_boundary(e: dict) -> str | None:
    blob = " ".join((e.get("name_ko", ""), e.get("industry", ""),
                     e.get("tech", ""), e.get("desc", "")))
    for name, rx in BOUNDARY.items():
        if rx.search(blob):
            return name
    return None


def select_sample(pool: list[dict], n: int = 40, seed: int = 42,
                  per_boundary: int = 4) -> tuple[list[dict], dict]:
    """경계 5유형 각 per_boundary + 나머지 무작위 → n개. (표본, 유형별 개수)."""
    rnd = random.Random(seed)
    by_b: dict[str, list[dict]] = {k: [] for k in BOUNDARY}
    rest: list[dict] = []
    for e in pool:
        b = _match_boundary(e)
        (by_b[b] if b else rest).append(e)

    chosen, seen = [], set()
    coverage = {}
    for name, lst in by_b.items():
        rnd.shuffle(lst)
        pick = lst[:per_boundary]
        coverage[name] = len(pick)
        for e in pick:
            if e["biz_no"] not in seen:
                chosen.append({**e, "_boundary": name}); seen.add(e["biz_no"])
    # 무작위 채움
    rnd.shuffle(rest)
    for e in rest:
        if len(chosen) >= n:
            break
        if e["biz_no"] not in seen:
            chosen.append({**e, "_boundary": None}); seen.add(e["biz_no"])
    # 경계 풀이 부족해 n 못 채우면 다른 경계에서 추가
    if len(chosen) < n:
        extra = [e for lst in by_b.values() for e in lst if e["biz_no"] not in seen]
        rnd.shuffle(extra)
        for e in extra:
            if len(chosen) >= n:
                break
            chosen.append({**e, "_boundary": _match_boundary(e)}); seen.add(e["biz_no"])
    return chosen[:n], coverage
