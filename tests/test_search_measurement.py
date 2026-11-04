"""Browser SERP import rules using only isolated, explicitly synthetic captures."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from am_seo.search_measurement import preserve_search_measurement, validate_search_measurement
from am_seo.workflow import WorkflowEngine


class NoCalls:
    def runtime(self):
        return {"available": True, "kind": "offline-test"}

    def __call__(self, *args, **kwargs):
        raise AssertionError("No provider may be called by a SERP import")


class SearchMeasurementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="amseo-search-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.plan = {"id": "fixture-dual-line-v1", "version": 1, "engine": "bing",
                     "settings": {"organic_only": True, "requested_location_verified": False},
                     "queries": [{"id": identifier, "locale": locale, "prompt": prompt} for identifier, locale, prompt in [
                         ("EN-M", "en-US", "Fixture mouse question?"), ("EN-A", "en-US", "Fixture AI device question?"),
                         ("ZH-M", "zh-CN", "测试鼠标问题？"), ("ZH-A", "zh-CN", "测试AI设备问题？")]]}
        self.plan_path = self.root / "config/search-panel.json"
        self.plan_path.parent.mkdir(parents=True)
        self.plan_path.write_text(json.dumps(self.plan, ensure_ascii=False), encoding="utf-8")
        self.engine = WorkflowEngine(self.root, runner=NoCalls())
        self.cycle = self.engine._new({"goal": "Offline import test", "market": "both", "channels": ["search"]})
        self.engine._save()

    def payload(self):
        records = []
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6BQQAAAAASUVORK5CYII=")
        for query in self.plan["queries"]:
            directory = self.root / "outputs/runtime/console/workflow" / self.cycle["id"] / "searchcaptures" / query["id"]
            directory.mkdir(parents=True, exist_ok=True)
            evidence, screenshot = directory / "dom.txt", directory / "screen.png"
            evidence.write_text("Synthetic offline SERP test fixture: " + query["prompt"], encoding="utf-8")
            screenshot.write_bytes(png)
            results = [{"rank": i, "title": "Synthetic offline organic result " + str(i),
                        "url": "https://example.com/result/" + str(i)} for i in range(1, 11)]
            if query["id"].endswith("M"):
                results[2]["url"] = "https://store.angrymiao.com/products/fixture"
            records.append({"query_id": query["id"], "locale": query["locale"], "platform": "bing",
                            "status": "completed", "captured_at_utc": "2026-11-01T11:00:00+00:00",
                            "page_url": "https://www.bing.com/search?q=" + quote(query["prompt"]),
                            "evidence_path": str(evidence.relative_to(self.root)), "evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                            "screenshot_path": str(screenshot.relative_to(self.root)), "screenshot_sha256": hashlib.sha256(png).hexdigest(),
                            "results": results})
        return {"executor": "current_chat_agent", "panel": deepcopy(self.plan),
                "panel_sha256": hashlib.sha256(self.plan_path.read_bytes()).hexdigest(), "observations": records}

    def test_actual_top10_rules_are_locale_separated_exact_domains_and_no_mixed_total(self):
        payload = self.payload()
        result = validate_search_measurement(self.root, self.cycle["id"], payload)
        self.assertIsNone(result["score"])
        self.assertEqual(result["completed"], 4)
        self.assertEqual([g["score"] for g in result["groups"]], [50, 50])
        self.assertEqual(result["observations"][0]["official_domain_ranks_top10"], [3])
        payload["observations"][0]["results"][2]["url"] = "https://store.angrymiao.com.evil.example/product"
        result = validate_search_measurement(self.root, self.cycle["id"], payload)
        self.assertFalse(result["observations"][0]["official_domain_present_top10"])
        self.assertEqual(result["groups"][0]["score"], 0)

    def test_positive_partial_top10_is_an_error_not_a_selective_success(self):
        payload = self.payload()
        payload["observations"][0]["results"] = payload["observations"][0]["results"][:5]
        result = validate_search_measurement(self.root, self.cycle["id"], payload)
        self.assertEqual(result["completed"], 3)
        record = result["observations"][0]
        self.assertEqual(record["status"], "error")
        self.assertIn("incomplete_top10", record["error"])
        self.assertIsNone(record["official_domain_present_top10"])
        self.assertEqual(result["groups"][0]["errors"], 1)

    def test_supplemental_screenshot_time_does_not_redate_source_capture(self):
        payload = self.payload()
        record = payload["observations"][0]
        record["capture_note"] = "Original page capture preserved; screenshot saved later."
        record["screenshot_captured_at_utc"] = "2026-11-02T01:00:00Z"
        result = validate_search_measurement(self.root, self.cycle["id"], payload)
        saved = result["observations"][0]
        self.assertEqual(saved["captured_at_utc"], "2026-11-01T11:00:00+00:00")
        self.assertEqual(saved["screenshot_captured_at_utc"], record["screenshot_captured_at_utc"])
        self.assertEqual(saved["capture_note"], record["capture_note"])

    def test_all_errors_remain_null_with_every_planned_attempt_retained(self):
        payload = self.payload()
        for record in payload["observations"]:
            record.update(status="error", results=[], error="Synthetic CAPTCHA fixture; no bypass")
        result = validate_search_measurement(self.root, self.cycle["id"], payload)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["attempted"], result["errors"])
        self.assertTrue(all(g["score"] is None for g in result["groups"]))

    def test_fixed_query_plan_identity_and_full_denominator_are_required(self):
        for mutate in [
            lambda p: p.update(executor="unknown_writer"),
            lambda p: p.update(panel_sha256="0" * 64),
            lambda p: p["panel"]["queries"][0].update(prompt="Easier replacement"),
            lambda p: p["observations"].pop(),
            lambda p: p["observations"][0].update(page_url="https://www.bing.com/search?q=Other"),
            lambda p: p["observations"][0].update(locale="zh-CN"),
        ]:
            payload = self.payload()
            mutate(payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_search_measurement(self.root, self.cycle["id"], payload)

    def test_capture_tamper_cross_cycle_paths_duplicate_and_out_of_order_results_rejected(self):
        payload = self.payload()
        path = self.root / payload["observations"][0]["evidence_path"]
        path.write_text("changed synthetic evidence")
        with self.assertRaisesRegex(ValueError, "hash"):
            validate_search_measurement(self.root, self.cycle["id"], payload)
        for mutation in [
            lambda p: p["observations"][0].update(evidence_path="config/search-panel.json"),
            lambda p: p["observations"][0]["results"][0].update(rank=2),
            lambda p: p["observations"][0]["results"][1].update(url="https://example.com/result/1"),
            lambda p: p["observations"][0]["results"][0].update(url="http://127.0.0.1/private"),
        ]:
            payload = self.payload()
            mutation(payload)
            with self.assertRaises(ValueError):
                validate_search_measurement(self.root, self.cycle["id"], payload)

    def test_import_preserves_geo_timestamps_technical_history_and_never_calls_provider(self):
        geo = {"status": "measured", "score": None, "observations": [{"captured_at_utc": "2026-10-31T10:00:00Z", "answer_text": "Synthetic answer fixture"}], "groups": []}
        technical = {"score": 88.9, "captured_at_utc": "2026-10-31T10:00:00Z"}
        self.cycle["metrics"] = {"measurement_id": "prior-fixture", "geo": deepcopy(geo), "seo": {"technical": deepcopy(technical)}, "evaluated_at": "2026-10-31T10:00:00Z"}
        result = self.engine.start("import-search-measurement", cycle_id=self.cycle["id"], payload=self.payload())
        metrics = result["cycle"]["metrics"]
        self.assertEqual(metrics["geo"], geo)
        self.assertEqual(metrics["seo"]["technical"], technical)
        self.assertEqual(len(result["cycle"]["metrics_history"]), 1)
        self.assertEqual(metrics["seo"]["completed"], 4)
        self.assertTrue((self.root / metrics["seo"]["manifest_path"]).is_file())
        self.assertFalse(result["cycle"].get("traces"))

    def test_later_geo_or_technical_measurement_does_not_erase_or_redate_serp(self):
        self.engine.start("import-search-measurement", cycle_id=self.cycle["id"], payload=self.payload())
        original = deepcopy(self.cycle["metrics"]["seo"])
        current = {"seo": {"status": "waiting_data", "score": None, "technical": {"score": 100}}, "geo": {"status": "error", "score": None}}
        preserved = preserve_search_measurement(self.cycle["metrics"], current)
        self.assertEqual(preserved["seo"]["observations"], original["observations"])
        self.assertEqual(preserved["seo"]["measurement_id"], original["measurement_id"])
        self.assertEqual(preserved["seo"]["measured_at_utc"], original["measured_at_utc"])
        self.assertEqual(preserved["seo"]["technical"], {"score": 100})
        self.assertEqual(preserved["geo"]["status"], "error")
        self.engine._active = True
        with self.assertRaisesRegex(ValueError, "已有工作流"):
            self.engine.start("import-search-measurement", cycle_id=self.cycle["id"], payload=self.payload())


if __name__ == "__main__":
    unittest.main()
