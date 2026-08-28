"""US FORGED — §4 배제 규칙(비스타트업 법인·해외법인).

판별 기준은 **사업자번호 형식**이지 사명이 아니다(Rooy, Inc. 같은 국내 법인의 영문명은
배제하면 안 됨). 해외법인은 사업자번호 3형식으로 잡는다: OC*·외국법인_*·해외법인
(전수 스캔상 각각 169·27·11 = 207건, engine_snapshot.normalize_biz_no 가 foreign 으로 분류).

법인격(투자목적회사·투자조합·SPC·N호 유한회사·지주[사명 끝])은 사명 패턴으로 배제하되
오탐(홀릭스팩토리의 '스팩', 이노스페이스 등)을 피하도록 정밀 패턴만 쓴다.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

# 배제 목록 = 공고 무관 global + 공고 전용 pack 병합(둘 다 같은 스키마).
_GLOBAL = Path(__file__).resolve().parent.parent / "config" / "global_exclusions.yaml"


def _load_cfg() -> dict:
    """global_exclusions.yaml + 활성 기준팩 exclusions.yaml 병합."""
    from engine import criteria_pack
    g = yaml.safe_load(_GLOBAL.read_text(encoding="utf-8")) or {} if _GLOBAL.exists() else {}
    p = criteria_pack.exclusions()
    out: dict = {}
    for key in ("exclusions", "established_suspects", "duplicate_merges"):
        out[key] = list(g.get(key, []) or []) + list(p.get(key, []) or [])
    return out


_C = _load_cfg()
KNOWN_EXCLUDED = {e["biz_no"]: e.get("reason", "명시 배제")
                  for e in _C.get("exclusions", [])}
ESTABLISHED_SUSPECT = {e["biz_no"]: e.get("note", "상장/대형 의심")
                       for e in _C.get("established_suspects", [])}


def established_suspect(row: dict) -> str | None:
    """상장/대형 의심(명시 목록) → note. 배제 아니라 T3 강등·플래그용."""
    return ESTABLISHED_SUSPECT.get(row.get("biz_no", ""))


# 법인격(사업 실체가 스타트업이 아님) — 정밀 패턴
_LEGAL = re.compile(
    r"투자목적회사|투자조합|벤처투자조합|신기술사업투자조합|사모투자|성장투자목적|"
    r"기업인수목적|유한책임회사|\d+\s*호\s*(?:유한회사|유한|투자조합|조합)")
# 지주는 사명 '끝'에 올 때만(××지주). 중간의 '지주'(지주막하 등) 오탐 방지.
_HOLDING_TAIL = re.compile(r"지주\s*$")


def entity_exclusion(row: dict) -> tuple[bool, str]:
    """(배제 여부, 사유). 명시 배제 목록 → 사업자번호 형식 → 사명 법인격 패턴."""
    if row.get("biz_no") in KNOWN_EXCLUDED:
        return True, f"명시 배제: {KNOWN_EXCLUDED[row['biz_no']]}"
    if row.get("biz_status") == "foreign":
        return True, f"해외법인(사업자번호 {row.get('biz_no_raw', '')})"
    name = (row.get("name_ko", "") or "").strip()
    if _LEGAL.search(name):
        return True, "비스타트업 법인격(투자목적회사·조합·SPC 등)"
    if _HOLDING_TAIL.search(name):
        return True, "지주회사(사명 말미 '지주')"
    return False, ""
