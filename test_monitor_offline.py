"""모니터링 오프라인 검증 — API 키/네트워크 불필요 (Gemini·requests 모킹).

python test_monitor_offline.py
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import config


class FakeAnswer:
    def __init__(self, text):
        self.text = text
        self.sources = []


class FakeGemini:
    """monitor 프롬프트별 고정 JSON 응답."""
    def __init__(self):
        self.call_count = 0
        self.prompts = []

    def plain(self, prompt, model=None, allowed_models=None):
        self.call_count += 1
        self.prompts.append(prompt)
        if '"next_deadline"' in prompt:
            return FakeAnswer(json.dumps({
                "next_deadline": "2026-10-11",
                "next_deadline_note": "Batch 36 마감 (rolling admission 병행)",
                "batches": [{"name": "Batch 36", "deadline": "2026-10-11",
                             "start": "2027 Q1", "location": "Palo Alto"}],
                "requirements": ["MVP 보유", "유료 고객 또는 활성 유저"],
                "funding_terms": "$150K for 6%",
                "program_format": "4개월 실리콘밸리 상주",
                "notes": "",
            }, ensure_ascii=False))
        if '"recent_companies"' in prompt:
            return FakeAnswer(json.dumps({
                "recent_companies": [{"name": "Acme AI", "batch": "Batch 35",
                                      "country": "KR", "sector": "AI SaaS",
                                      "one_liner": "B2B AI"}],
                "common_traits": {"sectors": "B2B SaaS·핀테크", "stage": "매출 초기",
                                  "geography": "미국+APAC", "business_model": "B2B",
                                  "team": "글로벌 경험 창업자"},
                "fit_advice": "영문 IR과 초기 매출이 있으면 유리.",
                "evidence_note": "샘플",
            }, ensure_ascii=False))
        if '"service_changes"' in prompt:
            return FakeAnswer(json.dumps({
                "service_changes": [{"what": "신규 프로그램 추가", "evidence": "diff"}],
                "pricing_changes": [],
                "people_changes": [{"who": "홍길동 (前 500 Global APAC 총괄)",
                                    "what": "멘토 영입", "evidence": "기사"}],
                "other_updates": [],
                "alert": True,
                "summary": "멘토 영입과 서비스 개편 감지.",
            }, ensure_ascii=False))
        raise AssertionError("알 수 없는 프롬프트")

    grounded = plain


class MonitorOfflineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="monitor_test_"))
        self._patches = [
            mock.patch.object(config, "CHECKPOINT_DIR", self.tmp / "checkpoints"),
            mock.patch.object(config, "SNAPSHOT_DIR", self.tmp / "checkpoints/snapshots"),
            mock.patch.object(config, "OUTPUT_DIR", self.tmp / "output"),
            mock.patch.object(config, "MONITOR_LOG_PATH", self.tmp / "checkpoints/monitor_log.jsonl"),
            mock.patch.object(config, "GLOBAL500_DEADLINE_LOG", self.tmp / "checkpoints/global500_deadline.jsonl"),
            mock.patch.object(config, "AC_TARGETS_JSON", self.tmp / "no_such.json"),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- common
    def test_snapshot_diff_and_change_detection(self):
        from monitors import common
        with mock.patch.object(common, "fetch_page_text",
                               side_effect=["서비스 A\n가격 100만원", "서비스 A\n가격 150만원\n신규 멘토"]):
            r1 = common.check_page("t", "home", "https://example.com")
            self.assertTrue(r1["first_seen"])
            self.assertFalse(r1["changed"])
            r2 = common.check_page("t", "home", "https://example.com")
            self.assertTrue(r2["changed"])
            self.assertIn("+가격 150만원", r2["diff"])
            self.assertIn("-가격 100만원", r2["diff"])

    def test_fetch_failure_keeps_snapshot(self):
        from monitors import common
        with mock.patch.object(common, "fetch_page_text", side_effect=["본문", ""]):
            common.check_page("t2", "home", "https://example.com")
            r = common.check_page("t2", "home", "https://example.com")
            self.assertTrue(r["fetch_failed"])
            self.assertFalse(r["changed"])
            self.assertEqual(common.load_snapshot("t2", "home")["text"], "본문")

    # ---------------------------------------------------------------- 500
    def test_global500_run(self):
        from monitors import common, global500
        fake = FakeGemini()
        with mock.patch.object(common, "fetch_page_text", return_value="Flagship page text"), \
             mock.patch.object(global500, "_search_news", return_value=[
                 {"title": "500 Global batch 36", "link": "http://n", "source": "s", "date": "2026-07-01"}]):
            path = global500.run(fake, use_ai=True)
        report = Path(path).read_text(encoding="utf-8")
        self.assertIn("2026-10-11", report)
        self.assertIn("Batch 36", report)
        self.assertIn("공통점 분석", report)
        self.assertEqual(fake.call_count, 2)
        # 마감일 이력 기록
        log_lines = (self.tmp / "checkpoints/global500_deadline.jsonl").read_text().splitlines()
        self.assertEqual(json.loads(log_lines[-1])["deadline"], "2026-10-11")

    def test_deadline_change_alert(self):
        from monitors import global500
        global500.track_deadline("2026-10-11", "")
        info = global500.track_deadline("2026-11-01", "")
        self.assertTrue(info["changed"])
        self.assertEqual(info["prev"], "2026-10-11")

    # ---------------------------------------------------------------- ac
    def test_ac_watch_run(self):
        from monitors import ac_watch, common
        fake = FakeGemini()
        with mock.patch.object(common, "fetch_page_text", return_value="회사 소개 서비스"), \
             mock.patch.object(ac_watch, "_search_news", return_value=[
                 {"title": "업라이트 멘토 영입", "link": "http://n", "source": "s", "date": "2026-07-10"}]):
            path = ac_watch.run(fake, use_ai=True)
        report = Path(path).read_text(encoding="utf-8")
        self.assertIn("Long Story Short", report)
        self.assertIn("Intralink", report)
        self.assertIn("비교 시트 갱신 필요", report)
        self.assertIn("멘토 영입", report)

    def test_ac_targets_json_override(self):
        from monitors import ac_watch
        override = self.tmp / "ac_targets.json"
        override.write_text(json.dumps([{"name": "X", "slug": "x", "pages": {},
                                         "news_queries": []}]), encoding="utf-8")
        with mock.patch.object(config, "AC_TARGETS_JSON", override):
            targets = ac_watch.load_targets()
        self.assertEqual([t["slug"] for t in targets], ["x"])

    def test_ac_no_ai_mode(self):
        from monitors import ac_watch, common
        with mock.patch.object(common, "fetch_page_text", return_value="본문"), \
             mock.patch.object(ac_watch, "_search_news", return_value=[]):
            path = ac_watch.run(client=None, use_ai=False)
        self.assertTrue(Path(path).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
