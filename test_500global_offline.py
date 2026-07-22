"""① 500 Global 모니터 오프라인 검증 — API 키/네트워크 불필요 (Gemini·requests 모킹).

python test_500global_offline.py
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
    """프롬프트별 고정 JSON 응답."""
    def __init__(self):
        self.call_count = 0

    def plain(self, prompt, model=None, allowed_models=None):
        self.call_count += 1
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
        raise AssertionError("알 수 없는 프롬프트")

    grounded = plain


class Global500OfflineTest(unittest.TestCase):
    def setUp(self):
        from monitors.global500 import config as g5cfg
        self.tmp = Path(tempfile.mkdtemp(prefix="g500_test_"))
        self._patches = [
            mock.patch.object(config, "CHECKPOINT_DIR", self.tmp / "checkpoints"),
            mock.patch.object(config, "SNAPSHOT_DIR", self.tmp / "checkpoints/snapshots"),
            mock.patch.object(config, "OUTPUT_DIR", self.tmp / "output"),
            mock.patch.object(config, "MONITOR_LOG_PATH", self.tmp / "checkpoints/monitor_log.jsonl"),
            mock.patch.object(g5cfg, "DEADLINE_LOG", self.tmp / "checkpoints/global500_deadline.jsonl"),
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
                               side_effect=["요건 A\n마감 10/11", "요건 A\n마감 11/01"]):
            r1 = common.check_page("t", "home", "https://example.com")
            self.assertTrue(r1["first_seen"])
            self.assertFalse(r1["changed"])
            r2 = common.check_page("t", "home", "https://example.com")
            self.assertTrue(r2["changed"])
            self.assertIn("+마감 11/01", r2["diff"])
            self.assertIn("-마감 10/11", r2["diff"])

    def test_fetch_failure_keeps_snapshot(self):
        from monitors import common
        with mock.patch.object(common, "fetch_page_text", side_effect=["본문", ""]):
            common.check_page("t2", "home", "https://example.com")
            r = common.check_page("t2", "home", "https://example.com")
            self.assertTrue(r["fetch_failed"])
            self.assertFalse(r["changed"])
            self.assertEqual(common.load_snapshot("t2", "home")["text"], "본문")

    # ---------------------------------------------------------------- run
    def test_run_produces_report_and_deadline_log(self):
        from monitors import common
        from monitors.global500 import crawler
        fake = FakeGemini()
        with mock.patch.object(common, "fetch_page_text", return_value="Flagship page text"), \
             mock.patch.object(crawler, "_search_news", return_value=[
                 {"title": "500 Global batch 36", "link": "http://n", "source": "s", "date": "2026-07-01"}]):
            path = crawler.run(fake, use_ai=True)
        report = Path(path).read_text(encoding="utf-8")
        self.assertIn("global500", str(Path(path).parent))  # output/global500/ 폴더 분리
        self.assertIn("2026-10-11", report)
        self.assertIn("Batch 36", report)
        self.assertIn("공통점 분석", report)
        self.assertIn("새 마감일 확인", report)  # 첫 실행 = 최초 발견 알림
        self.assertEqual(fake.call_count, 2)
        log_lines = (self.tmp / "checkpoints/global500_deadline.jsonl").read_text().splitlines()
        self.assertEqual(json.loads(log_lines[-1])["deadline"], "2026-10-11")

    def test_deadline_first_found_then_changed(self):
        from monitors.global500 import crawler
        info0 = crawler.track_deadline("", "미확인")
        self.assertFalse(info0["first_found"])
        info1 = crawler.track_deadline("2026-10-11", "")
        self.assertTrue(info1["first_found"])
        self.assertFalse(info1["changed"])
        info2 = crawler.track_deadline("2026-11-01", "")
        self.assertTrue(info2["changed"])
        self.assertEqual(info2["prev"], "2026-10-11")

    def test_dday_label(self):
        from monitors.global500 import crawler
        self.assertEqual(crawler._dday_label(5), " (D-5)")
        self.assertEqual(crawler._dday_label(0), " (D-0)")
        self.assertEqual(crawler._dday_label(-3), " (마감 지남 3일)")
        self.assertEqual(crawler._dday_label(None), "")

    def test_no_ai_mode(self):
        from monitors import common
        from monitors.global500 import crawler
        with mock.patch.object(common, "fetch_page_text", return_value="본문"), \
             mock.patch.object(crawler, "_search_news", return_value=[]):
            path = crawler.run(client=None, use_ai=False)
        self.assertTrue(Path(path).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
