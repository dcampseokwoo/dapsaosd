"""US FORGED — 스테이지 필터 (§3).

DB에 존재하는 모든 스테이지 값을 명시적으로 버킷에 매핑한다. 미매칭 값은 조용히
탈락시키지 않고 예외를 던진다(새 값이 들어오면 즉시 드러나게).

  IN_SCOPE     : Pre-seed, Angel, Seed
  UNKNOWN      : 알 수 없음, (결측)        → 통과시키되 별도 티어
  EXCEPTION    : Pre-A                     → pre_a_bucket() 로 미국+physical 여부 판단
  OUT_OF_SCOPE : Series A~E, Pre-B, Pre-IPO, IPO(*), M&A(*), 상장
"""
from __future__ import annotations

import re

IN_SCOPE = "IN_SCOPE"
UNKNOWN = "UNKNOWN"
EXCEPTION = "EXCEPTION"
OUT_OF_SCOPE = "OUT_OF_SCOPE"


class UnknownStageValue(Exception):
    """매핑에 없는 스테이지 값 — 조용히 처리하지 말고 예외."""


from engine import criteria_pack as _pack   # 활성 기준팩(스테이지 정책=공고 종속)

_SP = _pack.criteria()["stage_policy"]
_IN = re.compile(_SP["in_scope_pattern"], re.I)
_EXC = re.compile(_SP["exception_pattern"], re.I)
_OUT = re.compile(_SP["out_of_scope_pattern"], re.I)
_UNKNOWN = set(_SP.get("unknown_values", ["", "알 수 없음"]))


def stage_bucket(value) -> str:
    """스테이지 값 → 버킷. 미매칭은 UnknownStageValue."""
    s = "" if value is None else str(value).strip()
    if s in _UNKNOWN:
        return UNKNOWN
    if _IN.match(s):
        return IN_SCOPE
    if _EXC.match(s):
        return EXCEPTION
    if _OUT.match(s):
        return OUT_OF_SCOPE
    raise UnknownStageValue(f"미매칭 스테이지 값: {s!r}")


def pre_a_bucket(target: str, physical_product: bool) -> str:
    """Pre-A(EXCEPTION) 의 최종 처리: 미국 진출 + 물리적 제품이면 stage_exception, 아니면 배제.

    타겟 국가가 98.4% 결측인 DB에서 '미국' 명시는 극소수 강신호라 스테이지로 날리지 않는다.
    physical_product 는 §1 분류기가 준다(그 전엔 호출측이 판단/보류).
    """
    _rule = _SP.get("exception_rule", {})
    us = _rule.get("require_target_contains", "미국") in (target or "")
    return "stage_exception" if (us and physical_product) else OUT_OF_SCOPE


# 병합 시 '후기 채택' 정렬용 순위 (UNKNOWN 은 최하 → 알려진 스테이지가 이김)
_RANK = [
    ("unknown", -1), ("pre-seed", 0), ("angel", 1), ("seed", 2), ("pre-a", 3),
    ("series a", 4), ("pre-b", 5), ("series b", 6), ("series c", 7),
    ("series d", 8), ("series e", 9), ("pre-ipo", 10), ("ipo", 11), ("m&a", 11),
]


def stage_rank(value) -> int:
    s = ("" if value is None else str(value).strip()).lower()
    if s in ("", "알 수 없음"):
        return -1
    s = s.replace("프리", "pre-").replace("시리즈", "series ")
    for key, rank in sorted(_RANK, key=lambda x: -len(x[0])):
        if s.startswith(key):
            return rank
    return -1
