"""활성 기준팩(criteria pack) 로더 — "기준팩만 교체하면 다른 공고 평가"의 단일 진입점.

공고 종속 데이터(분류 프롬프트·스테이지 정책·모집 분야 enum·판정 규칙)를 `criteria/<id>/`
아래에 두고 여기서 읽는다. 활성 팩은 env `ENGINE_CRITERIA`(없으면 DEFAULT_CRITERIA).

이번 Phase(자산 분리)에서는 **로직을 옮기지 않는다** — 각 엔진 모듈이 기존 로직을 그대로
쓰되, 하드코딩돼 있던 공고 종속 '데이터'만 이 로더에서 공급받는다. 규칙엔진 구현은 Phase 6.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CRITERIA = "237489"        # US FORGED 공고 id


def active_id() -> str:
    return os.environ.get("ENGINE_CRITERIA", DEFAULT_CRITERIA)


def pack_dir(cid: str | None = None) -> Path:
    return ROOT / "criteria" / (cid or active_id())


_CACHE: dict[str, dict] = {}


def criteria(cid: str | None = None) -> dict:
    cid = cid or active_id()
    if cid not in _CACHE:
        _CACHE[cid] = json.loads((pack_dir(cid) / "criteria.json").read_text(encoding="utf-8"))
    return _CACHE[cid]


def prompt_text(cid: str | None = None) -> str:
    c = criteria(cid)
    return (pack_dir(cid) / c.get("prompt_ref", "prompt.md")).read_text(encoding="utf-8")


def exclusions(cid: str | None = None) -> dict:
    """공고 전용 배제 목록(criteria/<id>/exclusions.yaml). 없거나 비면 {}."""
    import yaml
    p = pack_dir(cid) / "exclusions.yaml"
    if p.exists():
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {}
