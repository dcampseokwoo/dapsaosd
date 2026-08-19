"""US FORGED 골든셋 회귀 하네스 (§5).

레이어별로 분리 검증한다(골든셋 설계):
  - classification_must_pass / must_fail : "이 회사가 하드테크인가" (스테이지 무관)
  - stage_rules.value_mapping            : 값 → 버킷 매핑만
  - malformed_biz_no                     : 사업자번호 정규화
파이프라인 후반 레이어(중복 병합·Pre-A 예외·불변식)는 해당 단계 구현 후 활성화한다.

현재는 baseline(현재 라벨 로직) 기준이라 다수가 실패한다 — 그 실패 목록이 개선의 기준.
"""
from __future__ import annotations

import pytest

from screening import uf_engine, uf_golden, uf_snapshot

GOLDEN = uf_golden.load_golden()


# ───────────────────────── 1. 분류: hardtech 여야 하는 기업
@pytest.mark.parametrize("entry", GOLDEN["classification_must_pass"],
                         ids=[e["name"] for e in GOLDEN["classification_must_pass"]])
def test_classification_must_pass(entry):
    verdict, rec = uf_golden.classification_verdict(entry)
    assert verdict == "hardtech", (
        f"{entry['name']}: hardtech 이어야 하는데 '{verdict}' — "
        f"소개문='{rec.get('desc', '')[:60]}' / trap={entry.get('trap', '')}")


# ───────────────────────── 2. 분류: hardtech 가 아니어야 하는 기업
@pytest.mark.parametrize("entry", GOLDEN["classification_must_fail"],
                         ids=[e["name"] for e in GOLDEN["classification_must_fail"]])
def test_classification_must_fail(entry):
    verdict, rec = uf_golden.classification_verdict(entry)
    assert verdict != "hardtech", (
        f"{entry['name']}: hardtech 가 아니어야 하는데 통과 — "
        f"기대 '{entry.get('expect_verdict', 'non-hardtech')}' / "
        f"소개문='{rec.get('desc', '')[:60]}'")


# ───────────────────────── 3. 스테이지: 값 → 버킷 매핑
@pytest.mark.parametrize("case", GOLDEN["stage_rules"]["value_mapping"],
                         ids=[str(c["value"]) for c in GOLDEN["stage_rules"]["value_mapping"]])
def test_stage_value_mapping(case):
    value, expect = case["value"], case["expect"]
    if expect == "RAISE":
        with pytest.raises(uf_engine.UnknownStageValue):
            uf_engine.stage_bucket(value)
    else:
        assert uf_engine.stage_bucket(value) == expect, (
            f"스테이지 '{value}': 기대 {expect}, 실제 {uf_engine.stage_bucket(value)}")


# ───────────────────────── 4. 사업자번호 정규화(malformed 감지)
@pytest.mark.parametrize("case", GOLDEN["malformed_biz_no"],
                         ids=[c["name"] for c in GOLDEN["malformed_biz_no"]])
def test_malformed_biz_no_flagged(case):
    _, status = uf_snapshot.normalize_biz_no(case["value"])
    assert status in ("malformed", "valid"), f"{case['name']}: status={status}"
    # 하이픈 위치 오류는 malformed 로 잡혀야 한다(조용히 통과 금지)
    if "725-870" in case["value"]:
        assert status == "malformed"


# ───────────────────────── 후반 레이어(구현 후 활성화)
@pytest.mark.skip(reason="§2 중복 병합 구현 후 활성화")
def test_duplicate_merge():
    ...


@pytest.mark.skip(reason="§3 Pre-A 예외 버킷 구현 후 활성화")
def test_pre_a_exception():
    ...


@pytest.mark.skip(reason="§6/§8 파이프라인 산출물 구현 후 활성화")
def test_invariants():
    ...
