"""Read bounded planning signals from the Todo store and completed question runs."""
import json
from pathlib import Path


def _read(path):
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def console_evidence(root):
    root = Path(root)
    workspace = _read(root / "outputs/geo-workspace/state.json")
    tasks = workspace.get("tasks") or []
    failures = []
    for task in tasks:
        if task.get("check_status") == "needs_work":
            check = task.get("verification") or {}
            failures.append({
                "task_id": task["id"], "checked_at": check.get("checked_at"),
                "failed_checks": [c.get("id") or c.get("title") for c in task.get("checks", [])
                                  if c.get("passed") is False][:8],
                "http_statuses": [e.get("status") for e in check.get("evidence", [])][:8],
            })
    result = {"todo_count": len(tasks), "failed_todo_checks": failures[:20]}
    directory = root / "outputs/runtime/console/question-lab/runs"
    # Run IDs are unordered. Choose by sampling time, not by file modification time.
    latest = {}
    for path in directory.glob("R-*/run.json"):
        run = _read(path)
        if (run.get("status") in {"completed", "partial"} and run.get("finished_at")
                and run["finished_at"] > latest.get("finished_at", "")):
            latest = run
    if latest:
        protocol = latest.get("protocol", {})
        result["api_observation"] = {
            "run_id": latest["id"], "panel_id": latest["panel_id"], "finished_at": latest["finished_at"],
            "scope": "api_brand_presence_only", "mode": protocol.get("mode"), "model": protocol.get("model"),
            "groups": [{key: group.get(key) for key in ("locale", "test_group", "hits", "successful_tests", "errors", "not_run")}
                       for group in latest.get("groups", [])][:8],
            "miss_ids": [row["id"] for row in latest.get("observations", [])
                         if row.get("status") in {"completed", "no_ai_answer"} and not row.get("hit")][:16],
        }
    return result
