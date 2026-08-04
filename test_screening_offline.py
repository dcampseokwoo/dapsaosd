"""프리스크리닝 엔진 오프라인 검증 — API 키/네트워크 불필요.

python test_screening_offline.py
"""
import unittest

from screening import backtest, dataset, rules


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
