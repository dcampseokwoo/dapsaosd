"""프리스크리닝 엔진 오프라인 검증 — API 키/네트워크 불필요.

python test_screening_offline.py
"""
import json
import unittest

from screening import (agreement, backtest, blind_fixture, dataset, experiment,
                       levels_fable, rules, rules_v2, rules_v3)


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


class TestFitRules(unittest.TestCase):
    """v2 신설 — Fit 도 규칙표가 계산한다(v1 은 정성 판단이라 결정성이 없었다)."""

    def test_fit_is_deterministic(self):
        sig = dataset.FIT["cardmonster"]
        first = rules_v2.fit_of(sig, rules.GATE_COND)
        for _ in range(10):
            self.assertEqual(rules_v2.fit_of(sig, rules.GATE_COND), first)

    def test_unknown_signal_is_not_negative(self):
        allyes = {k: "yes" for k in rules_v2.FIT_SIGNALS}
        base = rules_v2.fit_of(allyes, rules.GATE_PASS)[1]
        one_unknown = dict(allyes, momentum="unknown")
        one_no = dict(allyes, momentum="no")
        self.assertEqual(rules_v2.fit_of(one_unknown, rules.GATE_PASS)[1], base - 2)
        self.assertEqual(rules_v2.fit_of(one_no, rules.GATE_PASS)[1], base - 4)

    def test_stage_mismatch_caps_fit_at_mid(self):
        sig = {k: "yes" for k in rules_v2.FIT_SIGNALS} | {"stage_band_fit": "no"}
        grade, score, _ = rules_v2.fit_of(sig, rules.GATE_PASS)
        self.assertGreaterEqual(score, rules_v2.FIT_CUTOFF_HIGH)
        self.assertEqual(grade, rules_v2.FIT_MID)

    def test_gate_fail_skips_fit(self):
        self.assertEqual(rules_v2.fit_of(dataset.FIT["nthing"],
                                        rules.GATE_FAIL)[0], "해당 없음")

    def test_every_company_has_all_fit_signals(self):
        for key, sig in dataset.FIT.items():
            self.assertEqual(set(sig), set(rules_v2.FIT_SIGNALS), key)
            for k, v in sig.items():
                self.assertIn(v, ("yes", "no", "unknown"), f"{key}.{k}")

    def test_admitted_companies_are_high_fit(self):
        for r in backtest.run():
            if r["company"].ground_truth.startswith("admitted"):
                self.assertEqual(r["fit"], rules_v2.FIT_HIGH, r["company"].name)


class TestActionMapping(unittest.TestCase):
    def test_hold_is_never_a_rejection(self):
        a = rules_v2.action_of(rules_v2.TIER_HOLD, rules_v2.FIT_HIGH,
                               rules.GATE_COND, False)
        self.assertIn("설문", a)
        self.assertIn("탈락 아님", a)      # 탈락 통보로 오인되지 않게 문구에 명시
        self.assertNotIn("부적합", a)

    def test_low_fit_hold_skips_survey(self):
        """Fit 은 공개 신호로 확정 — Fit 낮음이면 설문 비용을 쓰지 않는다."""
        a = rules_v2.action_of(rules_v2.TIER_HOLD, rules_v2.FIT_LOW,
                               rules.GATE_COND, False)
        self.assertIn("설문 불필요", a)

    def test_good_quality_low_fit_goes_elsewhere(self):
        a = rules_v2.action_of("B 확인 후 추천", rules_v2.FIT_LOW,
                               rules.GATE_PASS, False)
        self.assertIn("타 프로그램", a)

    def test_every_company_gets_an_action(self):
        for r in backtest.run():
            self.assertTrue(r["action"], r["company"].name)

    def test_admitted_companies_are_not_dropped(self):
        """합격 4개사는 '추천' 또는 '설문 요청'이어야 한다 — 탈락·부적합 금지."""
        for r in backtest.run():
            if r["company"].ground_truth.startswith("admitted"):
                self.assertTrue(
                    "추천" in r["action"] or "설문" in r["action"],
                    f"{r['company'].name}: {r['action']}")


class TestRulesV3(unittest.TestCase):
    """v3 — 불확실성 전파. 라벨을 보지 않고 구조만으로 오탐을 줄이는가."""

    def test_known_axes_give_point_estimate(self):
        """모든 축이 확정이면 구간 폭 0 — v2 점추정과 같은 값."""
        lv = {"traction": 4, "team": 3, "market": 3, "moat": 2}
        iv = rules_v3.decide("500", lv, {})
        self.assertEqual(iv.lo, iv.hi)
        self.assertEqual(iv.width, 0)
        self.assertAlmostEqual(iv.lo, rules_v2.aggregate("500", lv).weighted)

    def test_unknown_axis_widens_interval(self):
        iv = rules_v3.decide("500", {"traction": 4, "team": 3,
                                     "market": None, "moat": 2}, {})
        self.assertGreater(iv.width, 0)
        self.assertEqual(iv.unknown_axes, ["market"])
        # 시장 가중치 0.2 × (5-1) = 0.8
        self.assertAlmostEqual(iv.width, 0.8)

    def test_only_adjacent_alternatives_count_as_boundary(self):
        """2단계 떨어진 대안은 경계 판정으로 보지 않는다(근거 없는 확대 방지)."""
        lv = {"traction": 3, "team": 4, "market": 3, "moat": 3}
        near = rules_v3.decide("500", lv, {"team": 3})
        far = rules_v3.decide("500", lv, {"traction": 1})
        self.assertIn("team", near.unstable_axes)
        self.assertEqual(far.unstable_axes, [])

    def test_confident_only_when_interval_clears_line(self):
        hi = rules_v3.decide("hax", {"trl": 4, "team": 4,
                                     "manufacturing": 3, "customer": 3}, {})
        self.assertEqual(hi.zone, rules_v3.ZONE_YES)
        lo = rules_v3.decide("500", {"traction": 3, "team": 2,
                                     "market": 3, "moat": 2}, {})
        self.assertEqual(lo.zone, rules_v3.ZONE_NO)
        mid = rules_v3.decide("500", {"traction": 4, "team": 3,
                                      "market": None, "moat": 2}, {})
        self.assertEqual(mid.zone, rules_v3.ZONE_HUMAN)

    def test_gate_fail_is_not_recommended(self):
        iv = rules_v3.decide("hax", {"trl": 5, "team": 5, "manufacturing": 5,
                                     "customer": 5}, {}, gate=rules.GATE_FAIL)
        self.assertEqual(iv.zone, rules_v3.ZONE_NO)

    def test_v3_catches_the_v2_false_positive(self):
        """핵심 회귀 테스트: SaaSMetrics(500 탈락)를 v3 는 단정하지 않는다."""
        r = backtest.evaluate(dataset.by_key("saasmetrics"))
        self.assertEqual(r["scores"]["v2"].tier, "B 확인 후 추천")   # v2 는 오탐
        self.assertEqual(r["v3"].zone, rules_v3.ZONE_HUMAN)          # v3 는 유보

    def test_v3_keeps_every_admit_out_of_rejection(self):
        for r in backtest.run():
            if r["company"].ground_truth.startswith("admitted"):
                self.assertNotEqual(r["v3"].zone, rules_v3.ZONE_NO,
                                    r["company"].name)


class TestExperiment(unittest.TestCase):
    """실험 결과를 고정한다 — 회귀 시 즉시 드러나게."""

    def setUp(self):
        self.results = backtest.run()

    def test_confident_decisions_have_no_error(self):
        """v3 가 단정한 건에 오류가 없어야 한다 (실험 2의 핵심 주장)."""
        e = experiment.exp2_confident(self.results)
        self.assertEqual(e["v3"]["wrong"], [])
        self.assertGreater(e["v3"]["decided"], 0)

    def test_v3_is_more_accurate_than_v2_where_it_decides(self):
        e = experiment.exp2_confident(self.results)
        self.assertGreater(e["v3"]["accuracy"], e["v2"]["accuracy"])
        self.assertLess(e["v3"]["coverage"], e["v2"]["coverage"])  # 대가는 커버리지

    def test_uncertainty_is_mostly_from_missing_data(self):
        """남은 불확실성이 규칙 탓이 아니라 자료 부재 탓임을 고정."""
        e = experiment.exp4_full_docs(self.results)
        self.assertGreater(e["unknown_share_of_width"], 0.5)

    def test_recommend_line_sits_on_a_stable_plateau(self):
        """3.25 가 우연이 아님 — 인접 구간에서도 정확도가 유지되는지."""
        rows = {r["line"]: r for r in experiment.exp3_line_sweep(self.results)}
        self.assertEqual(rows[3.25]["accuracy"], 1.0)
        self.assertEqual(rows[3.50]["accuracy"], 1.0)


class TestValidity(unittest.TestCase):
    """이 백테스트가 무엇을 주장할 수 있는지 자체를 고정한다."""

    def setUp(self):
        self.v = backtest.validity(backtest.run())

    def test_confirmed_rejections_are_tracked(self):
        """확정 불합격 표본 수를 지표에 노출 — 정밀도 주장의 근거이자 한계."""
        self.assertEqual(self.v["n_confirmed_rejected"],
                         sum(1 for c in dataset.COMPANIES
                             if c.ground_truth.startswith("rejected")))
        self.assertGreater(self.v["n_confirmed_rejected"], 0)

    def test_precision_claim_is_still_blocked(self):
        """표본 2개사로는 정밀도·특이도를 주장할 수 없음을 명시해야 한다."""
        self.assertTrue(any("정밀도" in m for m in self.v["not_measurable"]))
        self.assertTrue(any("근접 탈락" in m for m in self.v["not_measurable"]))

    def test_no_version_is_perfect(self):
        """어느 버전도 라벨 6개사를 다 맞히지 못함 — '완성' 주장 차단."""
        sb = backtest.scoreboard(backtest.run())
        for mode, r in sb.items():
            got, total = r["total"].split("/")
            self.assertLess(int(got), int(total), f"{mode} 가 만점이면 표본을 재검토")

    def test_agreement_signal_is_documented_as_failed(self):
        """버전 합의는 오탐을 잡지 못한다 — 나중에 신뢰도로 오용되지 않게 고정."""
        ag = backtest.agreement(backtest.run())
        self.assertFalse(ag["catches_false_positive"])
        self.assertIn("사용 금지", ag["conclusion"])

    def test_known_false_positive_is_surfaced(self):
        """SaaSMetrics(500 탈락)를 v2 가 추천하는 오탐 — 숨기지 말고 노출."""
        self.assertIn("SaaSMetrics", self.v["false_positives"])

    def test_in_sample_companies_are_flagged(self):
        """규칙 수정으로 구제된 기업은 반드시 in-sample 로 표기돼야 한다."""
        for key in backtest.RESCUED_BY:
            self.assertIn(dataset.by_key(key).name, self.v["in_sample"])

    def test_separation_admits_over_controls(self):
        """합격군 추천율이 대조군보다 높아야 한다 (판별력의 최소 조건)."""
        adm, ctl = self.v["separation"]
        self.assertGreater(adm, ctl)


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


class TestBlindAgreement(unittest.TestCase):
    """작업 1~3 — 블라인드 재분류 측정의 무결성."""

    def test_blind_input_has_no_leak(self):
        """블라인드 입력에 정답·기존 분류·비고가 새어들지 않는다."""
        rows = blind_fixture.build()
        self.assertEqual(len(rows), len(dataset.COMPANIES))
        for row in rows:
            self.assertEqual(set(row), set(blind_fixture.ALLOWED))
        text = json.dumps(rows, ensure_ascii=False)
        for bad in ("ground_truth", '"levels"', "LEVELS_V2", "fit_reason",
                    '"unstable"', "needs_confirm", '"note"', '"sources"'):
            self.assertNotIn(bad, text)

    def test_kappa_perfect_agreement_is_one(self):
        pairs = [(1, 1), (2, 2), (None, None), (5, 5), (3, 3), (None, None)]
        self.assertEqual(agreement.kappa(pairs), 1.0)

    def test_kappa_chance_level_is_zero(self):
        """관측 일치가 우연 기대치와 같으면 κ=0 (두 범주를 독립·균등 사용)."""
        pairs = [(1, 1), (1, 2), (2, 1), (2, 2)] * 5
        self.assertAlmostEqual(agreement.kappa(pairs), 0.0, places=3)

    def test_kappa_penalizes_chance(self):
        """일치율이 같아도 범주가 쏠리면 κ 는 낮아야 한다 — 단순 일치율과 다름."""
        skewed = [(1, 1)] * 9 + [(1, 2)]      # 일치 90%, 그러나 거의 전부 한 범주
        spread = [(i, i) for i in (1, 2, 3, 4, 5)] * 2
        self.assertLess(agreement.kappa(skewed), agreement.kappa(spread))

    def test_fable_covers_every_scored_axis(self):
        """독립 분류가 기존 분류와 같은 기업·축을 전부 다뤘는지."""
        self.assertEqual(set(levels_fable.LEVELS_FABLE), set(dataset.LEVELS_V2))
        for key, axes in dataset.LEVELS_V2.items():
            self.assertEqual(set(levels_fable.LEVELS_FABLE[key]), set(axes), key)
            for axis, (lv, why) in levels_fable.LEVELS_FABLE[key].items():
                self.assertTrue(lv is None or lv in (1, 2, 3, 4, 5), f"{key}.{axis}")
                self.assertTrue(why, f"{key}.{axis} 근거 누락")

    def test_confidence_is_recorded_for_every_axis(self):
        for key, axes in levels_fable.LEVELS_FABLE.items():
            for axis in axes:
                self.assertIn(levels_fable.CONFIDENCE[key][axis],
                              ("high", "low"), f"{key}.{axis}")

    def test_reclassified_only_touches_disagreed_axes(self):
        """작업 2-3 규칙: 일치했던 축은 건드리지 않는다."""
        base = agreement.axis_pairs(agreement.merged_fable(False))
        dis = {(r["key"], r["axis"]) for r in agreement.disagreements(base)}
        for key, axes in levels_fable.RECLASSIFIED.items():
            for axis in axes:
                self.assertIn((key, axis), dis, f"{key}.{axis} 는 일치했던 축")

    def test_improvement_raised_adjacent_agreement(self):
        """작업 2-3 합격 기준: 개선이 인접 일치율을 실제로 올렸는지 고정."""
        imp = agreement.improvement_effect()
        self.assertIsNotNone(imp)
        self.assertGreater(imp["overall_after"]["adjacent"],
                           imp["overall_before"]["adjacent"])

    def test_no_admit_is_confirmed_rejected_in_either_classification(self):
        """두 분류 모두에서 합격사가 v3 `확정 비추천`으로 떨어지지 않는다."""
        for results in (backtest.run(), agreement.run_with_fable(True)):
            for r in results:
                if r["company"].ground_truth.startswith("admitted"):
                    self.assertNotEqual(r["v3"].zone, rules_v3.ZONE_NO,
                                        r["company"].name)

    def test_live_selected_companies_are_not_rejected(self):
        """실전 선발 2개사(디캠프×500 1기)는 보강 팩트 기준으로도 걸러지면 안 된다."""
        from screening import live_eval
        for key in live_eval.ENRICHED:
            r = live_eval.evaluate(key)
            self.assertNotEqual(r["v3"].zone, rules_v3.ZONE_NO, key)
            self.assertFalse(r["v2"].tier.startswith(("C", "D")), key)
            self.assertNotEqual(r["gate"], rules.GATE_FAIL, key)

    def test_swap_restores_dataset(self):
        """run_with_fable 이 dataset 전역 상태를 원상 복구하는지."""
        before = {k: dict(v) for k, v in dataset.LEVELS_V2.items()}
        unstable_before = {c.key: dict(c.unstable) for c in dataset.COMPANIES}
        agreement.run_with_fable(True)
        self.assertEqual(dataset.LEVELS_V2, before)
        for c in dataset.COMPANIES:
            self.assertEqual(c.unstable, unstable_before[c.key])


class TestRouterV4(unittest.TestCase):
    """v4 다신호 라우터 — 오분류 자기검출."""

    def setUp(self):
        from screening import router_v4
        self.r = router_v4

    def test_clear_hardware_routes_hax(self):
        out = self.r.route("Robotics", "로봇, 제조", "자율 하역 로봇 개발")
        self.assertEqual(out["track"], "hax")
        self.assertEqual(out["confidence"], "high")

    def test_clear_software_routes_500(self):
        out = self.r.route("Financial Services", "핀테크", "대출 비교 플랫폼 앱")
        self.assertEqual(out["track"], "500")

    def test_therapeutic_routes_indiebio(self):
        out = self.r.route("Bio", "신약", "항체 기반 면역항암 신약 개발")
        self.assertEqual(out["track"], "bio_routing")

    def test_digital_therapeutic_is_not_bio(self):
        """디지털 치료제·진단은 IndieBio 가 아니다 (SW)."""
        out = self.r.route("Healthcare", "AI", "digital therapeutics 앱")
        self.assertNotEqual(out["track"], "bio_routing")

    def test_empty_input_is_out_of_scope(self):
        self.assertEqual(self.r.route("", "", "")["track"], "대상외")

    def test_conflicting_signals_flag_low_confidence(self):
        """HW(기술 태그)·SW(사업 소개)가 접전이면 라우팅 불안정으로 플래그."""
        out = self.r.route("", "센서", "센서 데이터 대시보드 플랫폼")
        self.assertEqual(out["confidence"], "low")


class TestGateV4(unittest.TestCase):
    """v4 스테이지 3분할 게이트."""

    def setUp(self):
        from screening import gate_v4
        self.g = gate_v4

    def test_seed_is_scoreable(self):
        z = self.g.gate({"track": "500", "confidence": "high"}, "Seed")
        self.assertEqual(z["zone"], self.g.ZONE["SCORE"])

    def test_series_a_is_human_review(self):
        z = self.g.gate({"track": "500", "confidence": "high"}, "Series A")
        self.assertEqual(z["zone"], self.g.ZONE["HUMAN"])

    def test_series_b_is_scaleup_not_reject(self):
        """시리즈B 이상은 '탈락'이 아니라 '스케일업 트랙 안내'."""
        z = self.g.gate({"track": "hax", "confidence": "high"}, "Series B")
        self.assertEqual(z["zone"], self.g.ZONE["SCALEUP"])

    def test_low_conf_routing_goes_to_human_check(self):
        z = self.g.gate({"track": "hax", "confidence": "low"}, "Seed")
        self.assertEqual(z["zone"], self.g.ZONE["RCHECK"])

    def test_empty_input_out_of_scope(self):
        z = self.g.gate({"track": "대상외", "confidence": "none"}, "")
        self.assertEqual(z["zone"], self.g.ZONE["OOS"])

    def test_v4_halves_human_review_vs_v3(self):
        """재설계 효과 고정: v4 사람 검토가 v3 보다 확연히 적다."""
        from screening import gbd_pipeline
        v3 = gbd_pipeline.run()
        v4 = gbd_pipeline.run_v4()
        h3 = sum(1 for r in v3 if "사람 검토" in r["outcome"])
        h4 = sum(1 for r in v4 if r["outcome"] == self.g.ZONE["HUMAN"])
        self.assertLess(h4, h3 * 0.75)


class TestDisqualifiersV7(unittest.TestCase):
    """v7 확정 탈락 — 확인된 부적합만 탈락, 나머지는 메일(사람검토 폐지)."""

    def setUp(self):
        from screening import disqualifiers, engine_programs
        self.d = disqualifiers
        self.ep = engine_programs

    def _rec(self, sector="SW", tech="", desc="", stage="Seed"):
        return {"sector": sector, "tech": tech, "desc": desc, "stage": stage,
                "name_en": "x", "svc": ""}

    def test_series_b_is_hard_reject(self):
        c = self.d.check("500", "SW", "", "", "Series B")
        self.assertTrue(any("스테이지 이탈" in r for r in c["fails"]))

    def test_hax_series_a_is_hard_reject(self):
        """HAX 는 프리시드~시드 전용 — 시리즈A도 확정 탈락."""
        c = self.d.check("hax", "로봇", "제조", "", "Series A")
        self.assertTrue(c["fails"])

    def test_500_series_a_is_not_reject_anymore(self):
        """사람검토 폐지 — 500 시리즈A 는 탈락 아니라 메일 대상."""
        r = self.ep.eval_program("500", self._rec(stage="Series A"))
        self.assertEqual(r["zone"], self.d.Z_MAIL)

    def test_confirmed_no_english_is_hard_reject(self):
        c = self.d.check("500", "SW", "", "", "Seed", signals={"english": "no"})
        self.assertTrue(c["fails"])

    def test_confirmed_no_product_is_hard_reject(self):
        c = self.d.check("500", "SW", "", "", "Seed", signals={"product": "no"})
        self.assertTrue(c["fails"])

    def test_unconfirmed_disqualifier_becomes_mail(self):
        """확인 안 된 disqualifier 는 탈락 아님 → 메일 대상."""
        r = self.ep.eval_program("500", self._rec(stage="Seed"))
        self.assertEqual(r["zone"], self.d.Z_MAIL)

    def test_hax_excluded_field_is_hard_reject(self):
        c = self.d.check("hax", "핀테크", "결제", "블록체인 결제 하드월렛", "Seed")
        self.assertTrue(any("분야 부적합" in r for r in c["fails"]))

    def test_v7_reject_is_reason_tagged(self):
        """모든 확정 탈락은 사유가 붙는다(운영자가 큐를 비울 수 있게)."""
        from screening import gbd_pipeline
        for r in gbd_pipeline.run_v6():
            if r["outcome"] == self.d.Z_FAIL:
                self.assertTrue(r["reasons"], r["name_ko"])


class TestEngineV7(unittest.TestCase):
    """v7 — 분야 기반 · 사람검토 폐지 · 2갈래 판정."""

    def setUp(self):
        from screening import engine_programs, disqualifiers
        self.ep = engine_programs
        self.dq = disqualifiers

    def test_two_programs_are_configured_separately(self):
        self.assertEqual(self.ep.PROGRAMS["500"]["axes"],
                         ("traction", "team", "market", "moat"))
        self.assertEqual(self.ep.PROGRAMS["hax"]["axes"],
                         ("trl", "team", "manufacturing", "customer"))

    def test_same_company_differs_by_program(self):
        """같은 하드웨어 시리즈A: 500=메일 대상 / HAX=확정 탈락."""
        rec = {"sector": "Hardware", "tech": "로봇", "desc": "산업 로봇",
               "stage": "Series A", "name_en": "x", "svc": ""}
        r500 = self.ep.eval_program("500", rec)
        rhax = self.ep.eval_program("hax", rec)
        self.assertEqual(r500["zone"], self.dq.Z_MAIL)   # 사람검토 폐지
        self.assertEqual(rhax["zone"], self.dq.Z_FAIL)   # HAX 시리즈A = 탈락

    def test_cross_referral_hax_to_500(self):
        """HAX 탈락(시리즈A 하드웨어) → 500 후보로 리퍼럴."""
        rec = {"sector": "Hardware", "tech": "로봇", "desc": "산업 로봇",
               "stage": "Series A", "name_en": "x", "svc": ""}
        self.assertEqual(self.ep.cross_referral("hax", rec), "500")

    def test_no_human_review_bucket(self):
        """엔진 출력에 '사람 검토' 버킷이 존재하지 않는다."""
        from screening import gbd_pipeline
        human = sum(1 for r in gbd_pipeline.run_v6() if "사람 검토" in r["outcome"])
        self.assertEqual(human, 0)

    def test_two_bucket_outcomes_only(self):
        """판정은 확정 탈락 / 메일 대상 / IndieBio / 대상외 로만 구성."""
        from screening import gbd_pipeline
        allowed = {self.dq.Z_FAIL, self.dq.Z_MAIL, self.dq.Z_BIO, self.dq.Z_OOS,
                   self.ep.Z_DUAL}
        for r in gbd_pipeline.run_v6():
            self.assertIn(r["outcome"], allowed, r["name_ko"])

    def test_stage_scaleup_dominates_rejections(self):
        """스테이지 이탈이 확정 탈락의 주력(시리즈B+/IPO/M&A 제대로 걸림)."""
        from screening import gbd_pipeline
        rows = gbd_pipeline.run_v6()
        fails = [r for r in rows if r["outcome"] == self.dq.Z_FAIL]
        stage_fails = sum(1 for r in fails if "스테이지 이탈" in (r["reasons"] or ""))
        self.assertGreater(stage_fails, len(fails) * 0.7)


class TestSectorTaxonomy(unittest.TestCase):
    """표준 섹터 분류 축 — 자유텍스트를 표준키로 정규화(엔진 척추)."""

    def setUp(self):
        from screening import sectors
        self.s = sectors

    def test_variants_normalize_to_same_key(self):
        """핀테크 표기 변형이 모두 같은 표준키로 수렴한다."""
        for t in ("핀테크", "금융", "fintech", "결제 서비스"):
            self.assertIn("핀테크", self.s.classify(t), t)

    def test_track_of_canonical_sectors(self):
        self.assertEqual(self.s.track_of("로보틱스·자동화"), "hax")
        self.assertEqual(self.s.track_of("핀테크"), "500")
        self.assertEqual(self.s.track_of("바이오치료제"), "bio")

    def test_track_scores_counts_distinct_sectors(self):
        sc = self.s.track_scores("로봇 소재 배터리")   # 3개 하드테크 섹터
        self.assertGreaterEqual(sc["hax"], 3)
        self.assertEqual(sc["500"], 0)


class TestFieldRouting(unittest.TestCase):
    """분야(field) 기반 라우팅 — 업종은 거친 prior, 분야가 authoritative."""

    def setUp(self):
        from screening import router_v4
        self.r = router_v4

    def test_field_overrides_coarse_industry(self):
        """업종=Hardware여도 사업 실체가 SW면 분야=500(업종≠분야 신호)."""
        out = self.r.route("Hardware", "", "AI 기반 커머스 추천 플랫폼")
        self.assertEqual(out["track"], "500")
        self.assertTrue(out["mismatch"])          # 업종(hax) ≠ 분야(500)

    def test_field_confirms_hardware(self):
        """업종=Hardware이고 실체도 하드웨어면 HAX(불일치 없음)."""
        out = self.r.route("Hardware", "로봇", "산업용 로봇 팔 제조")
        self.assertEqual(out["track"], "hax")
        self.assertFalse(out["mismatch"])

    def test_field_variants_route_identically(self):
        """분야 표기 변형이 소개에 있으면 동일 트랙으로 수렴."""
        for t in ("금융 결제", "fintech 서비스", "핀테크 대출"):
            self.assertEqual(self.r.route("", "", t)["track"], "500", t)

    def test_route_exposes_field(self):
        out = self.r.route("Hardware", "", "리튬 이차전지 셀 제조")
        self.assertEqual(out["field"], "배터리·에너지")


class TestConfigSSOT(unittest.TestCase):
    """프로그램 기준이 programs.PROGRAMS(SSOT) 한 곳에서 나온다."""

    def setUp(self):
        from screening import programs, disqualifiers, engine_programs
        self.p = programs
        self.d = disqualifiers
        self.ep = engine_programs

    def test_engine_programs_uses_shared_config(self):
        """engine_programs.PROGRAMS 는 programs.py SSOT 를 그대로 참조한다."""
        self.assertIs(self.ep.PROGRAMS, self.p.PROGRAMS)

    def test_excluded_sectors_are_canonical_keys(self):
        """HAX 제외 섹터는 표준키로 선언된다(자유텍스트 아님)."""
        from screening import sectors
        for k in self.p.excluded_sectors("hax"):
            self.assertIn(k, sectors.TAXONOMY, k)

    def test_stage_policy_drives_verdict(self):
        """config stage_policy 를 바꾸면 판정이 따라간다(로직 하드코딩 아님)."""
        # HAX 는 시리즈A=FAIL 정책 → 확정 탈락
        self.assertEqual(self.d.stage_verdict("hax", "Series A")[0], "FAIL")
        # 500 은 시리즈A=OK 정책(사람검토 폐지) → 탈락 아님
        self.assertEqual(self.d.stage_verdict("500", "Series A")[0], "OK")

    def test_hax_excluded_field_gate_reads_config(self):
        """핀테크(표준키, config 제외분야)면 HAX 확정 탈락."""
        c = self.d.check("hax", "핀테크", "결제", "간편 결제 앱", "Seed")
        self.assertTrue(any("분야 부적합" in r for r in c["fails"]))

    def test_hardware_with_incidental_sw_word_not_excluded(self):
        """하드웨어 문맥에 SW 단어가 섞여도 오탈락하지 않는다(우선분야 동반 시)."""
        c = self.d.check("hax", "로보틱스", "로봇", "결제 단말 로봇 하드웨어", "Seed")
        self.assertFalse(any("분야 부적합" in x for x in c["fails"]))


class TestUsForged(unittest.TestCase):
    """US FORGED(디캠프 x HAX Hardtech Pre-Program) 공고 요건 필터."""

    def setUp(self):
        from screening import us_forged
        self.uf = us_forged

    def _rec(self, sector="", tech="", desc="", stage="Seed", target=""):
        return {"sector": sector, "tech": tech, "desc": desc, "stage": stage,
                "target": target, "svc": "", "name_ko": "x", "name_en": "x"}

    def test_hardtech_seed_is_eligible(self):
        e = self.uf.eligible(self._rec(sector="Hardware", tech="로봇",
                                       desc="산업용 로봇 팔"))
        self.assertTrue(e["status"].startswith("적합"))

    def test_software_only_is_rejected(self):
        e = self.uf.eligible(self._rec(sector="Software",
                                       desc="SaaS 회계 솔루션 플랫폼"))
        self.assertEqual(e["status"], "부적합")

    def test_series_a_hardtech_is_rejected(self):
        """Pre-Seed~Seed 전용 — 하드테크여도 시리즈A는 부적합."""
        e = self.uf.eligible(self._rec(sector="Hardware", tech="로봇",
                                       desc="산업 로봇", stage="Series A"))
        self.assertEqual(e["status"], "부적합")

    def test_us_seed_hardtech_is_immediate(self):
        e = self.uf.eligible(self._rec(sector="Hardware", tech="로봇",
                                       desc="로봇", stage="Seed", target="미국"))
        self.assertEqual(e["status"], "적합(즉시 후보)")

    def test_business_word_not_battery_false_positive(self):
        """'business'의 ess 가 배터리·에너지로 오분류되지 않는다."""
        from screening import sectors
        self.assertNotIn("배터리·에너지",
                         sectors.classify("accounting solution for business"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
