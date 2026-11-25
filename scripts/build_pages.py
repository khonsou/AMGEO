#!/usr/bin/env python3
"""Build the read-only GitHub Pages site from committed project observations."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ASSETS = {
    "index.html": "pages/index.html",
    "pages.css": "pages/pages.css",
    "pages.js": "pages/pages.js",
    "styles.css": "src/am_seo/web/styles.css",
    "lifestyle.css": "src/am_seo/web/lifestyle.css",
    "studio-desk.webp": "src/am_seo/web/studio-desk.webp",
}
CHECKS = {"passed": "passed", "needs_work": "failed"}


def text(value):
    if not isinstance(value, str):
        raise ValueError("Expected text in a public snapshot field.")
    return value


def instructions(values):
    if not isinstance(values, list):
        raise ValueError("Expected a list of instructions.")
    return [text(item) for item in values]


def count(value):
    if type(value) is not int or value < 0:
        raise ValueError("Expected a non-negative integer in a public count.")
    return value


def public_group(group):
    result = {key: text(group[key]) for key in ("locale", "test_group")}
    for key in ("hits", "successful_tests", "errors", "not_run", "planned"):
        result[key] = count(group[key])
    score = group["score"]
    if score is not None and (type(score) not in (float, int) or not 0 <= score <= 100):
        raise ValueError("Invalid score in the published GEO report.")
    return {**result, "score": score}


def sample_time(report):
    value = datetime.fromisoformat(text(report["verified_at"]))
    if value.tzinfo is None:
        raise ValueError("GEO timestamps require an explicit timezone.")
    return value


def public_cycle(cycle):
    if cycle is None:
        return None
    return {
        **{key: count(cycle[key]) for key in ("number", "strategy_version", "total", "ready", "verified")},
        **{key: text(cycle[key]) for key in ("market", "updated_at")},
    }


def public_snapshot(workspace, playbook, measurement, overview):
    if overview.get("geo") and sample_time(overview["geo"]) >= sample_time(measurement):
        measurement = overview["geo"]
    return {
        "cycle": public_cycle(overview.get("cycle")),
        "todo_updated_at": text(workspace["updated_at"]),
        "tasks": [
            {
                "title": text(task["title"]),
                "kind": text(task["kind"]),
                "done": task.get("execution_done") is True,
                "check": CHECKS.get(task.get("check_status"), "not_checked"),
                "steps": instructions(task["steps"]),
                "acceptance": instructions(task["acceptance"]),
            }
            for task in workspace["tasks"]
        ],
        "question_updated_date": text(playbook["updated_date"]),
        "intents": {
            key: text(playbook["intents"][key]["label"])
            for key in ("find", "alternatives", "how", "facts")
        },
        "questions": [
            {key: text(question[key]) for key in ("prompt", "locale", "intent")}
            for question in playbook["questions"]
        ],
        "geo": {
            **{key: text(measurement[key]) for key in ("verified_at", "provider", "model")},
            "groups": [public_group(group) for group in measurement["groups"]],
        },
    }


def build(root, destination):
    if destination.is_symlink() or (
        destination.exists() and (not destination.is_dir() or any(destination.iterdir()))
    ):
        raise ValueError("Choose a new or empty output directory.")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()

    def committed_json(path):
        data = subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=root)
        return json.loads(data)

    overview_path = "outputs/geo-workspace/public-overview.json"
    overview_exists = subprocess.check_output(["git", "ls-tree", "--name-only", revision, "--", overview_path], cwd=root)
    snapshot = public_snapshot(
        committed_json("outputs/geo-workspace/state.json"),
        committed_json("config/geo-playbook.json"),
        committed_json("outputs/geo-workspace/todo-delivery-verification.json"),
        committed_json(overview_path) if overview_exists else {},
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        stage = Path(tmp) / "site"
        stage.mkdir()
        for name, path in ASSETS.items():
            shutil.copyfile(root / path, stage / name)
        (stage / "snapshot.json").write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        (stage / ".nojekyll").touch()
        stage.replace(destination)
    return revision


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="new or empty output directory")
    args = parser.parse_args()
    try:
        revision = build(ROOT, args.destination)
    except (KeyError, TypeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Pages build failed: {exc}\n")
    print(f"Built {args.destination} with observations from {revision}.")
