"""§2 중복 병합 강화 회귀 테스트 — 정규화 사명 + 1자리차 + 수동 병합 목록.

최종 라운드에서 사용자가 지적한 발송 리스트 중복 4쌍을 잠근다:
  워커린스페이스(동일 사업자번호·표기차) / 아폴론·크로스포인트(1자리차) / 티아이(수동목록).
"""
from engine import engine_dedup


def _rows(*specs):
    """(name, biz_no, stage) 튜플 → resolve_entities 입력 행. 유효 사업자번호라 uid=biz_no."""
    out = []
    for name, biz, stage in specs:
        out.append({"name_ko": name, "biz_no": biz, "biz_no_raw": biz, "stage": stage,
                    "biz_status": "valid", "uid": biz, "desc": "", "industry": ""})
    return out


def _by_biz(ents):
    return {e["biz_no"]: e for e in ents}


def test_one_digit_diff_helper():
    assert engine_dedup.is_one_digit_diff("661-81-02253", "667-81-02253")   # 아폴론
    assert engine_dedup.is_one_digit_diff("367-87-02674", "364-87-02674")   # 크로스포인트
    assert not engine_dedup.is_one_digit_diff("563-88-23981", "563-88-02981")  # 오믈렛=2자리차
    assert not engine_dedup.is_one_digit_diff("661-81-02253", "661-81-02253")  # 동일


def test_norm_name_strips_legal_forms():
    assert engine_dedup._norm_name("주식회사 워커린스페이스") == engine_dedup._norm_name("워커린스페이스")
    assert engine_dedup._norm_name("(주)티아이") == engine_dedup._norm_name("티아이")
    assert engine_dedup._norm_name("(주)유티아이") != engine_dedup._norm_name("티아이")


def test_same_biz_different_spelling_merges():
    """워커린스페이스: 동일 사업자번호인데 표기만 다름 → 1개 엔티티."""
    ents = engine_dedup.resolve_entities(_rows(
        ("주식회사 워커린스페이스", "236-87-03233", "Seed"),
        ("워커린스페이스", "236-87-03233", "Seed")))
    assert len(ents) == 1
    assert ents[0]["identity"] == "canonical_valid"


def test_one_digit_diff_merges():
    """아폴론·크로스포인트: 사명 동일 + 1자리차 → 병합."""
    ap = engine_dedup.resolve_entities(_rows(
        ("아폴론", "661-81-02253", "Pre-A"), ("아폴론", "667-81-02253", "Pre-A")))
    assert len(ap) == 1 and ap[0]["identity"] == "canonical_valid"
    assert set(ap[0]["merged_from"]) == {"661-81-02253", "667-81-02253"}


def test_two_digit_diff_not_merged_but_flagged():
    """오믈렛류(2자리차): 병합 금지 + similar_biz_no_suspect 플래그."""
    ents = engine_dedup.resolve_entities(_rows(
        ("오믈렛", "563-88-23981", "Seed"), ("오믈렛", "563-88-02981", "Seed")))
    assert len(ents) == 2
    assert all(e["identity"] == "name_collision" for e in ents)
    assert all("similar_biz_no_suspect" in e["flags"] for e in ents)


def test_manual_merge_from_config():
    """티아이: 1자리차 아님이지만 config duplicate_merges 로 강제 병합."""
    ents = engine_dedup.resolve_entities(_rows(
        ("티아이", "647-85-02411", "Seed"), ("(주)티아이", "671-81-00456", "Seed")))
    assert len(ents) == 1, "config duplicate_merges 로 병합돼야 함"


def test_genuinely_different_same_name_stays_collision():
    """한국공장지붕태양광지주: 사명 동일하나 사업자번호 대차 → 별개(name_collision)."""
    ents = engine_dedup.resolve_entities(_rows(
        ("한국공장지붕태양광지주", "727-81-02043", "Seed"),
        ("한국공장지붕태양광지주", "597-88-01495", "Seed")))
    assert len(ents) == 2
    assert all(e["identity"] == "name_collision" for e in ents)
