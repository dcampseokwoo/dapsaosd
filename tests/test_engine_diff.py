"""§7 스냅샷 diff 기계부 테스트 (후보 영향은 파이프라인 완성 후)."""
from __future__ import annotations

import pytest

from engine import engine_diff, engine_snapshot

SNAP = engine_snapshot.DEFAULT_SNAPSHOT


def test_resolve_snapshot_picks_frozen():
    assert engine_snapshot.resolve_snapshot().name.startswith("GBD_DB_")


def test_self_diff_is_empty():
    rows = engine_snapshot.load_rows(SNAP)
    d = engine_diff.column_diff(rows, rows)
    assert d["summary"] == {"added": 0, "removed": 0, "changed": 0}


def test_column_diff_detects_stage_change():
    a = [{"biz_no": "111-11-11111", "name_ko": "A", "stage": "Seed", "industry": "",
          "target": "", "name_en": "", "desc": "", "foundation_type": "", "investor": ""}]
    b = [{"biz_no": "111-11-11111", "name_ko": "A", "stage": "Series C", "industry": "",
          "target": "", "name_en": "", "desc": "", "foundation_type": "", "investor": ""}]
    d = engine_diff.column_diff(a, b)
    assert d["changed"]["111-11-11111"]["cols"]["stage"] == ["Seed", "Series C"]
    assert d["stage_transitions"] == {"Seed → Series C": 1}


def test_candidate_impact_deferred_without_pipeline():
    with pytest.raises(NotImplementedError):
        engine_diff.candidate_impact([], [], shortlist_fn=None)


def test_candidate_impact_with_injected_shortlist():
    old = [{"biz_no": "1"}, {"biz_no": "2"}]
    new = [{"biz_no": "2"}, {"biz_no": "3"}]
    imp = engine_diff.candidate_impact(old, new, shortlist_fn=lambda rs: {r["biz_no"] for r in rs})
    assert imp["entered"] == ["3"] and imp["left"] == ["1"] and imp["stayed"] == 1
