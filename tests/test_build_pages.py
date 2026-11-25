"""Regression coverage for the public Pages snapshot and its release boundary."""
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from scripts.build_pages import ASSETS, build, public_snapshot


class PagesBuildTests(unittest.TestCase):
    def test_export_uses_committed_data_and_an_explicit_release_manifest(self):
        with TemporaryDirectory() as folder:
            root = Path(folder) / "repo"
            root.mkdir()
            marker = "private-fixture-only"
            workspace = {
                "updated_at": "2026-01-02T01:00:00Z", "traffic": marker, "history": [marker],
                "tasks": [{
                    "title": "Public task", "kind": "page", "steps": ["Review public page"],
                    "acceptance": ["Page loads"], "check_status": "needs_work",
                    "execution_done": True, "verification": {"evidence": marker},
                }],
            }
            playbook = {
                "updated_date": "2026-01-01",
                "questions": [{"prompt": "Which product?", "intent": "find", "locale": "en-US", "extra": marker}],
                "intents": {key: {"label": key, "other": marker} for key in ("find", "alternatives", "how", "facts")},
            }
            measurement = {
                "verified_at": "2026-01-01T10:00:00Z", "provider": "example", "model": "test",
                "groups": [{"locale": "en-US", "test_group": "discovery", "score": 0, "hits": 0,
                            "successful_tests": 2, "errors": 1, "not_run": 1, "planned": 4, "answers": [marker]}],
            }
            state_path = root / "outputs/geo-workspace/state.json"
            for path, value in [(state_path, workspace), (root / "config/geo-playbook.json", playbook),
                                (state_path.with_name("todo-delivery-verification.json"), measurement)]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            for name, path in ASSETS.items():
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_text(name)
            background = b"RIFF\x10\x00\x00\x00WEBP\x00\xff"
            (root / ASSETS["studio-desk.webp"]).write_bytes(background)

            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "config", "outputs"], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                            "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
                            "commit", "-qm", "Fixture"], cwd=root, check=True)
            state_path.write_text("local edits must never enter a release")
            (root / "pages/local-backup.txt").write_text(marker)
            destination = Path(folder) / "site"
            destination.mkdir()
            build(root, destination)
            self.assertEqual({p.name for p in destination.iterdir()}, set(ASSETS) | {".nojekyll", "snapshot.json"})
            self.assertEqual((destination / "studio-desk.webp").read_bytes(), background)
            public = (destination / "snapshot.json").read_text()
            self.assertNotIn(marker, public)
            data = json.loads(public)
            self.assertEqual(data["tasks"][0]["check"], "failed")
            self.assertIs(data["tasks"][0]["done"], True)
            self.assertEqual(data["geo"]["verified_at"], measurement["verified_at"])
            group = data["geo"]["groups"][0]
            self.assertEqual([group[k] for k in ("score", "successful_tests", "errors", "not_run")], [0, 2, 1, 1])

    def test_reviewed_overview_can_supply_newer_observations_without_exposing_raw_fields(self):
        workspace = {"updated_at": "2026-01-01", "tasks": []}
        playbook = {"updated_date": "2026-01-01", "questions": [],
                    "intents": {key: {"label": key} for key in ("find", "alternatives", "how", "facts")}}
        measurement = {"verified_at": "2026-01-03T03:00:00Z", "provider": "test", "model": "old", "groups": []}
        cycle = {"number": 5, "strategy_version": 3, "total": 4, "ready": 3, "verified": 1,
                 "updated_at": "2026-01-04", "market": "both", "private_notes": "omit"}
        overview = {"cycle": cycle, "geo": {**measurement, "verified_at": "2026-01-03T12:00:00+08:00",
                                               "model": "new", "responses": ["omit"]}}
        snapshot = public_snapshot(workspace, playbook, measurement, overview)
        self.assertEqual(snapshot["geo"]["model"], "new")
        self.assertEqual(snapshot["cycle"]["verified"], 1)
        self.assertNotIn("omit", json.dumps(snapshot))
        overview["geo"]["verified_at"] = "2026-01-03T08:00:00+08:00"
        self.assertEqual(public_snapshot(workspace, playbook, measurement, overview)["geo"]["model"], "old")

    def test_an_existing_nonempty_directory_is_preserved(self):
        with TemporaryDirectory() as folder:
            destination = Path(folder)
            existing = destination / "unrelated.txt"
            existing.write_text("keep")
            with self.assertRaisesRegex(ValueError, "empty"):
                build(destination, destination)
            self.assertEqual(existing.read_text(), "keep")
