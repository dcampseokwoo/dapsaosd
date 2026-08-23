"""§4 배제 규칙 + 파이프라인 disposition 테스트."""
from __future__ import annotations

from screening import uf_exclude, uf_snapshot


def _row(name="x", biz="123-45-67890", status=None):
    b, st = uf_snapshot.normalize_biz_no(biz)
    return {"name_ko": name, "biz_no": b, "biz_no_raw": biz,
            "biz_status": status or st}


def test_foreign_oc_excluded():
    assert uf_exclude.entity_exclusion(_row("Zhongxing", "OC160024"))[0] is True


def test_foreign_label_excluded():
    assert uf_exclude.entity_exclusion(_row("어떤회사", "외국법인_싱가포르1"))[0] is True
    assert uf_exclude.entity_exclusion(_row("어떤회사", "해외법인"))[0] is True


def test_domestic_english_name_not_excluded():
    """Rooy, Inc. 처럼 정상 사업자번호를 가진 국내 법인 영문명은 배제 금지."""
    assert uf_exclude.entity_exclusion(_row("Rooy, Inc.", "123-45-67890"))[0] is False


def test_legal_entity_excluded():
    assert uf_exclude.entity_exclusion(_row("에스티이차전지성장투자목적회사"))[0] is True
    assert uf_exclude.entity_exclusion(_row("엔피코어오토메이션9호 유한회사"))[0] is True


def test_holding_tail_only():
    assert uf_exclude.entity_exclusion(_row("한국공장지붕태양광지주"))[0] is True
    # '지주막하'처럼 중간에 오면 배제 안 함
    assert uf_exclude.entity_exclusion(_row("지주막하출혈진단"))[0] is False


def test_spac_substring_not_false_positive():
    """'홀릭스팩토리'의 '스팩' 부분매칭으로 오배제되면 안 된다."""
    assert uf_exclude.entity_exclusion(_row("홀릭스팩토리"))[0] is False
