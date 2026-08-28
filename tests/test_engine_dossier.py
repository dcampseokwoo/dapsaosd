"""Phase 2 도시에 스키마·마이그레이션 회귀 테스트.

- derive() 는 결정적(타임스탬프 없음)이고 8축을 모두 채운다.
- 핵심 유도 매핑(software_only→SOFTWARE_ONLY, therapeutics→DRUG, consumer_facing→PERSONAL).
- 기존 캐시 전량을 유도했을 때 verdict 역산 일치율이 회귀하지 않는다(≥ 90%).
- end_use 정의(최종 기여)가 consumer_facing 을 PERSONAL 로 잡는다.
"""
from engine import engine_classify as C, engine_dossier as D


def _entry(**kw):
    base = dict(verdict="hardtech", matched_program_field="Industrial Hardware",
                physical_product=True, consumer_facing_end_product=False,
                maturity_signal="", evidence="근거 원문", confidence="high",
                prompt_version="v6", biz_no="000-00-00000")
    base.update(kw)
    return base


def test_all_axes_present():
    d = D.derive(_entry())
    assert set(d["axes"]) == set(D.AXES)
    for rec in d["axes"].values():
        assert set(rec) >= {"value", "evidence", "source", "needs_generation"}


def test_deterministic_no_timestamp():
    d1 = D.derive(_entry())
    d2 = D.derive(_entry())
    assert d1 == d2, "derive 는 결정적이어야 함(재생성 diff 방지)"
    assert "migrated_at" not in d1["provenance"]


def test_software_only_maps_physical():
    d = D.derive(_entry(verdict="software_only", physical_product=False))
    assert d["axes"]["physical_product"]["value"] == "SOFTWARE_ONLY"


def test_therapeutics_maps_drug_and_physical():
    d = D.derive(_entry(verdict="therapeutics", physical_product=False))
    assert d["axes"]["regulatory_class"]["value"] == "DRUG"
    assert d["axes"]["physical_product"]["value"] == "YES"     # 약(물질)도 물리적 제품
    assert D.back_derive_verdict(d) == "therapeutics"


def test_end_use_personal_from_consumer_facing():
    # "누구에게 파는가"가 아니라 최종 기여 대상 — consumer_facing 이면 PERSONAL
    d = D.derive(_entry(verdict="hardtech", consumer_facing_end_product=True))
    assert d["axes"]["end_use"]["value"] == "PERSONAL"


def test_nonderivable_axes_flagged():
    d = D.derive(_entry())   # 일반 B2B hardtech
    assert d["axes"]["tech_ownership"]["needs_generation"] is True
    assert d["axes"]["value_chain_position"]["needs_generation"] is True


def test_back_derivation_rate_not_regressed():
    """기존 캐시 전량 유도 → verdict 역산 ≥ 90%. (제품축 실질 ~95%)"""
    cache = C.load_cache()
    match = total = 0
    for entry in cache.values():
        d = D.derive(entry, None, normalize_field=C.normalize_field)
        total += 1
        if D.back_derive_verdict(d) == entry.get("verdict"):
            match += 1
    assert total > 0
    assert match / total >= 0.90, f"역산 일치율 회귀: {match}/{total}"
