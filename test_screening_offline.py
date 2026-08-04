"""프리스크리닝 엔진 오프라인 검증 — API 키/네트워크 불필요.

python test_screening_offline.py
"""
import unittest

from screening import backtest, dataset, rules, rules_v2


class TestRules(unittest.TestCase):
    def test_weights_sum_to_one(self):
        for track, w in rules.WEIGHTS.items():
            self.assertAlmostEqual(sum(w.values()), 1.0, msg=track)

    def test_deterministic(self):
        """같은 레벨 입력 → 항상 같은 Tier (엔진의 핵심 설계 원칙)."""
        lv = {"traction": 4, "team": 3, "market": 3, "moat": 2}
        first = rules.aggregate("500", lv, "strict")
        for _ in range(20):
            s = rules.aggregate("500", lv, "strict")
            self.assertEqual((s.weighted, s.tier), (first.weighted, first.tier))

    def test_demotion_rule(self):
        """L1 축이 있으면 가중평균이 높아도 Tier 는 C 를 넘지 못한다."""
        s = rules.aggregate("hax", {"trl": 5, "team": 5, "manufacturing": 5,
                                    "customer": 1}, "strict")
        self.assertGreater(s.weighted, 4.0)
        self.assertEqual(s.tier, "C 보완 후 재도전")
        self.assertTrue(s.demoted)

    def test_credibility_worst_wins(self):
        self.assertEqual(rules.credibility_overall(
            {"a": rules.CRED_OK, "b": rules.CRED_BROKEN, "c": rules.CRED_WARN}),
            rules.CRED_BROKEN)

    def test_credibility_collapse_caps_traction(self):
        s = rules.aggregate("500", {"traction": 5, "team": 5, "market": 5, "moat": 5},
                            "strict", credibility=rules.CRED_BROKEN)
        self.assertEqual(s.used_axes["traction"], 2)

    def test_neutral_mode_renormalizes(self):
        """`확인 필요` 축을 빼고 남은 가중치로 재정규화 — 감점이 아니다."""
        lv = {"traction": None, "team": 4, "market": 4, "moat": 4}
        strict = rules.aggregate("500", lv, "strict")
        neutral = rules.aggregate("500", lv, "neutral")
        self.assertEqual(neutral.weighted, 4.0)
        self.assertLess(strict.weighted, neutral.weighted)
        self.assertEqual(neutral.unknown_axes, ["traction"])

    def test_all_unknown_is_undecidable(self):
        lv = {"traction": None, "team": None, "market": None, "moat": None}
        self.assertEqual(rules.aggregate("500", lv, "neutral").tier, "판정 불가")


class TestRulesV2(unittest.TestCase):
    """v1 에서 드러난 4개 결함이 실제로 고쳐졌는지."""

    def test_weights_unchanged(self):
        """가중치는 디캠프 내부 루브릭 — v2 도 건드리지 않는다."""
        self.assertEqual(rules_v2.WEIGHTS, rules.WEIGHTS)

    def test_band_tables_cover_every_band(self):
        for track, bands in (("500", rules_v2.BAND_TRACTION),
                             ("hax", rules_v2.BAND_TRL)):
            for band in ("프리시드", "시드 초기", "시드 후기", "A 이후"):
                t = rules_v2.band_table(track, band)
                self.assertEqual(sorted(t), [1, 2, 3, 4, 5], f"{track}/{band}")

    def test_preseed_can_reach_top_tier(self):
        """v1 의 핵심 결함: 프리시드는 만점을 받아도 A 에 못 갔다."""
        perfect = {"traction": 5, "team": 5, "market": 5, "moat": 5}
        self.assertEqual(rules_v2.aggregate("500", perfect).tier, "A 추천")

    def test_unknown_axis_is_not_a_penalty(self):
        """`확인 필요` 축은 감점이 아니라 제외 — 남은 축의 평균이 그대로 나온다."""
        s = rules_v2.aggregate("500", {"traction": 4, "team": 4,
                                       "market": None, "moat": None})
        self.assertEqual(s.weighted, 4.0)
        self.assertEqual(sorted(s.unknown_axes), ["market", "moat"])

    def test_low_coverage_holds_instead_of_rejecting(self):
        """커버리지 미달 → 탈락이 아니라 보류."""
        s = rules_v2.aggregate("500", {"traction": None, "team": None,
                                       "market": 2, "moat": None})
        self.assertEqual(s.tier, rules_v2.TIER_HOLD)
        self.assertIsNone(s.weighted)

    def test_hax_customer_l1_does_not_demote(self):
        """HAX 는 고객 없는 랩 단계에 투자한다 — 고객 L1 은 강등 사유가 아니다."""
        lv = {"trl": 4, "team": 4, "manufacturing": 3, "customer": 1}
        v1 = rules.aggregate("hax", lv, "strict")
        v2 = rules_v2.aggregate("hax", lv)
        self.assertTrue(v1.demoted)
        self.assertFalse(v2.demoted)
        self.assertIn(v2.tier, rules.PASS_TIERS)

    def test_core_axis_l1_still_demotes(self):
        """반대로 핵심축(TRL/Team) L1 은 v2 에서도 강등된다."""
        lv = {"trl": 1, "team": 5, "manufacturing": 5, "customer": 5}
        self.assertTrue(rules_v2.aggregate("hax", lv).demoted)

    def test_v2_does_not_reject_actual_admits(self):
        """회귀 테스트: 실제 합격 기업을 C/D 로 떨어뜨리면 실패."""
        results = backtest.run()
        for r in results:
            if r["company"].ground_truth.startswith("admitted"):
                self.assertFalse(backtest.rejected(r, "v2"),
                                 f"{r['company'].name} 오탈락")

    def test_v2_stays_selective(self):
        """재현율을 올리느라 전부 통과시키면 스크리너가 아니다."""
        mt = backtest.metrics(backtest.run())
        self.assertLess(mt["modes"]["v2"]["pass_rate"], 0.5)


class TestGates(unittest.TestCase):
    def test_bio_is_routed_not_scored(self):
        r = backtest.evaluate(dataset.by_key("bredis"))
        self.assertTrue(r["routed"])
        self.assertEqual(r["scores"], {})

    def test_hax_excluded_sector_fails(self):
        r = backtest.evaluate(dataset.by_key("jobis"))   # 핀테크 SW → HAX 제외
        self.assertEqual(r["gate"], rules.GATE_FAIL)

    def test_late_stage_hax_fails(self):
        r = backtest.evaluate(dataset.by_key("nthing"))  # 시리즈C 하드웨어
        self.assertEqual(r["gate"], rules.GATE_FAIL)

    def test_late_stage_500_escalates_not_rejects(self):
        r = backtest.evaluate(dataset.by_key("safetics"))  # 시리즈A
        self.assertEqual(r["gate"], rules.GATE_HUMAN)

    def test_no_prototype_fails(self):
        r = backtest.evaluate(dataset.by_key("wavedeck"))
        self.assertEqual(r["gate"], rules.GATE_FAIL)


class TestBacktest(unittest.TestCase):
    def setUp(self):
        self.results = backtest.run()
        self.mt = backtest.metrics(self.results)

    def test_every_company_evaluated(self):
        self.assertEqual(len(self.results), len(dataset.COMPANIES))

    def test_engine_actually_discriminates(self):
        """전 기업이 한 칸에 몰리면 스크리너로서 무용 — 최소 3개 판정군."""
        for mode in backtest.MODES:
            dist = self.mt["modes"][mode]["distribution"]
            self.assertGreaterEqual(len(dist), 3, mode)
            self.assertLess(max(dist.values()) / self.mt["n_scored"], 0.7, mode)

    def test_pass_rate_is_selective(self):
        for mode in backtest.MODES:
            self.assertLess(self.mt["modes"][mode]["pass_rate"], 0.5, mode)

    def test_report_renders(self):
        body = backtest.render_report(self.results, self.mt)
        self.assertIn("전체 판정표", body)
        for c in dataset.COMPANIES:
            self.assertIn(c.name, body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
