"""② AC 업체 모니터 오프라인 검증 — API 키/네트워크 불필요 (Gemini·requests 모킹).

python test_ac_watch_offline.py
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
    def __init__(self):
        self.call_count = 0

    def plain(self, prompt, model=None, allowed_models=None):
        self.call_count += 1
        assert '"service_changes"' in prompt
        return FakeAnswer(json.dumps({
            "service_changes": [{"what": "신규 프로그램 추가", "evidence": "diff"}],
            "pricing_changes": [],
            "people_changes": [{"who": "홍길동 (前 500 Global APAC 총괄)",
                                "what": "멘토 영입", "evidence": "기사"}],
            "other_updates": [],
            "alert": True,
            "summary": "멘토 영입과 서비스 개편 감지.",
        }, ensure_ascii=False))


class AcWatchOfflineTest(unittest.TestCase):
    def setUp(self):
        from monitors.ac_watch import config as accfg
        self.tmp = Path(tempfile.mkdtemp(prefix="ac_test_"))
        self._patches = [
            mock.patch.object(config, "CHECKPOINT_DIR", self.tmp / "checkpoints"),
            mock.patch.object(config, "SNAPSHOT_DIR", self.tmp / "checkpoints/snapshots"),
            mock.patch.object(config, "OUTPUT_DIR", self.tmp / "output"),
            mock.patch.object(config, "MONITOR_LOG_PATH", self.tmp / "checkpoints/monitor_log.jsonl"),
            mock.patch.object(accfg, "TARGETS_JSON", self.tmp / "no_such.json"),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_produces_report(self):
        from monitors import common
        from monitors.ac_watch import watcher
        fake = FakeGemini()
        with mock.patch.object(common, "fetch_page_text", return_value="회사 소개 서비스"), \
             mock.patch.object(watcher, "_search_news", return_value=[
                 {"title": "업라이트 멘토 영입", "link": "http://n", "source": "s", "date": "2026-07-10"}]):
            path = watcher.run(fake, use_ai=True)
        self.assertIn("ac_watch", str(Path(path).parent))  # output/ac_watch/ 폴더 분리
        report = Path(path).read_text(encoding="utf-8")
        self.assertIn("Long Story Short", report)
        self.assertIn("Intralink", report)
        self.assertIn("비교 시트 갱신 필요", report)
        self.assertIn("멘토 영입", report)

    def test_targets_json_override(self):
        from monitors.ac_watch import config as accfg, watcher
        override = self.tmp / "ac_targets.json"
        override.write_text(json.dumps([{"name": "X", "slug": "x", "pages": {},
                                         "news_queries": []}]), encoding="utf-8")
        with mock.patch.object(accfg, "TARGETS_JSON", override):
            targets = watcher.load_targets()
        self.assertEqual([t["slug"] for t in targets], ["x"])

    def test_only_slug_filter(self):
        from monitors import common
        from monitors.ac_watch import watcher
        with mock.patch.object(common, "fetch_page_text", return_value="본문"), \
             mock.patch.object(watcher, "_search_news", return_value=[]):
            path = watcher.run(client=None, use_ai=False, only_slug="intralink")
        report = Path(path).read_text(encoding="utf-8")
        self.assertIn("Intralink", report)
        self.assertNotIn("Long Story Short", report)
        with self.assertRaises(SystemExit):
            watcher.run(client=None, use_ai=False, only_slug="없는업체")

    def test_no_ai_skips_gemini(self):
        from monitors import common
        from monitors.ac_watch import watcher
        fake = FakeGemini()
        with mock.patch.object(common, "fetch_page_text", return_value="본문"), \
             mock.patch.object(watcher, "_search_news", return_value=[]):
            watcher.run(fake, use_ai=False)
        self.assertEqual(fake.call_count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
