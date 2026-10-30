"""Offline-first project commands; never import or execute upstream code.

The checked-out project's paths are anchored to this module, not the shell's
working directory. No command reads API key values or starts provider calls.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Sequence

from . import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_KIT = PROJECT_ROOT / "outputs" / "agent-kit"
UPSTREAM_LOCK = PROJECT_ROOT / "config" / "upstreams.lock.json"

# These fields contain declared capability states, not credential material.
CAPABILITY_FIELDS = (
    "date",
    "public_evidence",
    "local_file_editing",
    "local_browser_regression",
    "site_source_repository",
    "commerce_admin",
    "search_console_analytics",
    "consumer_ai_sessions",
    "paid_search_model_api",
    "production_publish_scope",
    "note",
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _capabilities() -> dict[str, Any]:
    declared = _load_json(AGENT_KIT / "capabilities.json")
    return {key: declared[key] for key in CAPABILITY_FIELDS if key in declared}


def _project_path(value: str) -> Path:
    """Explicit user paths are absolute, or relative to the project checkout."""
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def _task_summary() -> dict[str, Any]:
    contract = _load_json(AGENT_KIT / "tasks.json")
    tasks = contract.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("tasks.json must contain a tasks array")
    summarized = []
    for task in tasks:
        if not isinstance(task, dict) or not task.get("id") or not task.get("status"):
            raise ValueError("Each task must have an id and status")
        summarized.append(
            {
                key: task[key]
                for key in (
                    "id",
                    "agent",
                    "action",
                    "status",
                    "completion_scope",
                    "missing_capability_or_data",
                )
                if key in task
            }
        )
    return {
        "task_count": len(summarized),
        "counts": dict(sorted(Counter(task["status"] for task in summarized).items())),
        "tasks": summarized,
        "runtime_status": contract.get("runtime_status"),
        "updated_date": contract.get("updated_date"),
    }


def project_status() -> dict[str, Any]:
    release_path = AGENT_KIT / "release-manifest.json"
    release = _load_json(release_path) if release_path.exists() else {}
    return {
        "project": "Angry Miao SEO/GEO",
        "version": __version__,
        "project_root": str(PROJECT_ROOT),
        **_task_summary(),
        "capabilities": _capabilities(),
        "release": {
            key: release[key]
            for key in ("status", "production_writes", "payload_status")
            if key in release
        },
        "scope": "Task and capability declarations; no authenticated connection probe or live execution.",
    }


def _emit_json(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def command_status(as_json: bool) -> int:
    result = project_status()
    if as_json:
        _emit_json(result)
    else:
        print(f"Angry Miao SEO/GEO {__version__}")
        print(f"Project: {PROJECT_ROOT}")
        print("Tasks: " + ", ".join(f"{count} {state}" for state, count in result["counts"].items()))
        for task in result["tasks"]:
            print(f"  {task['id']}  {task['status']}: {task.get('action', '')}")
        print(f"Release: {result['release'].get('status', 'not_recorded')}")
        print("Completed tasks describe local artifacts; see the task contract for deployment scope.")
    return 0


def _upstream_checks() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    result: dict[str, Any] = {"lock_file": str(UPSTREAM_LOCK), "repositories": []}
    if not UPSTREAM_LOCK.exists():
        checks.append({"name": "upstream_lock", "status": "pending", "detail": "Upstream lock file is not connected; local offline commands remain available."})
        return checks, result
    try:
        lock = _load_json(UPSTREAM_LOCK)
        upstreams = lock.get("upstreams")
        if not isinstance(upstreams, list):
            raise ValueError("upstreams.lock.json must contain an upstreams array")
    except (OSError, ValueError) as error:
        checks.append({"name": "upstream_lock", "status": "warning", "detail": str(error)})
        return checks, result
    checks.append({"name": "upstream_lock", "status": "ok", "detail": f"{len(upstreams)} pinned upstream entries; no upstream code imported."})
    git = shutil.which("git")
    for index, entry in enumerate(upstreams):
        repo: dict[str, Any] = {"name": entry.get("name", f"entry-{index}")} if isinstance(entry, dict) else {"name": f"entry-{index}"}
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            repo.update(status="warning", detail="Lock entry has no valid local path.")
        else:
            path = (PROJECT_ROOT / entry["path"]).resolve()
            repo.update(path=str(path), expected_commit=entry.get("commit"))
            if not path.is_relative_to(PROJECT_ROOT):
                repo.update(status="warning", detail="Upstream path is outside this project; not inspected.")
            elif not path.is_dir():
                repo.update(status="pending", detail="Pinned upstream has not been fetched.")
            elif not git:
                repo.update(status="warning", detail="git is unavailable; checkout commit not verified.")
            else:
                try:
                    probe = subprocess.run(
                        [git, "-C", str(path), "rev-parse", "--verify", "HEAD"],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=10,
                    )
                    current = probe.stdout.strip() if probe.returncode == 0 else None
                    repo["current_commit"] = current
                    expected = entry.get("commit")
                    if current and expected and current == expected:
                        repo.update(status="ok", detail="Local HEAD matches the pinned commit.")
                    elif current:
                        repo.update(status="warning", detail="Local HEAD does not match a recorded pin; run deps verify.")
                    else:
                        repo.update(status="warning", detail="Local directory is not a readable Git checkout.")
                except (OSError, subprocess.TimeoutExpired):
                    repo.update(status="warning", detail="Local git metadata probe failed or timed out.")
        result["repositories"].append(repo)
        checks.append({"name": f"upstream:{repo['name']}", "status": repo["status"], "detail": repo["detail"]})
    return checks, result


def doctor_status() -> dict[str, Any]:
    checks: list[dict[str, Any]] = [
        {
            "name": "python_runtime",
            "status": "ok" if sys.version_info >= (3, 11) else "error",
            "detail": f"Python {sys.version.split()[0]}; requires Python >=3.11.",
        }
    ]
    for filename in ("tasks.json", "capabilities.json", "validate_batch.py", "score_observations.py"):
        present = (AGENT_KIT / filename).is_file()
        checks.append({"name": f"agent_kit:{filename}", "status": "ok" if present else "error", "detail": "Present" if present else "Required local artifact is missing."})
    checks.append({"name": "git_runtime", "status": "ok" if shutil.which("git") else "pending", "detail": "Available" if shutil.which("git") else "Needed for upstream verification; offline validation is still available."})
    helper_exists = (PROJECT_ROOT / "scripts" / "sync_upstreams.py").is_file()
    checks.append({"name": "upstream_verify_helper", "status": "ok" if helper_exists else "pending", "detail": "Present" if helper_exists else "scripts/sync_upstreams.py is not connected yet."})
    upstream_checks, upstreams = _upstream_checks()
    checks.extend(upstream_checks)
    capabilities: dict[str, Any] = {}
    try:
        capabilities = _capabilities()
    except (OSError, ValueError) as error:
        checks.append({"name": "capability_declarations", "status": "error", "detail": str(error)})
    for key in (
        "site_source_repository",
        "commerce_admin",
        "search_console_analytics",
        "consumer_ai_sessions",
        "paid_search_model_api",
        "production_publish_scope",
    ):
        declaration = capabilities.get(key, "not_declared")
        available = declaration in ("available", "connected", "authorized", "ready")
        checks.append({"name": f"connection:{key}", "status": "ok" if available else "pending", "detail": f"Declared state: {declaration}. Not authenticated or network-probed by doctor."})
    has_error = any(item["status"] == "error" for item in checks)
    has_pending = any(item["status"] in ("warning", "pending") for item in checks)
    return {
        "project": "Angry Miao SEO/GEO",
        "project_root": str(PROJECT_ROOT),
        "status": "error" if has_error else "offline_ready_pending_connections" if has_pending else "ready",
        "checks": checks,
        "capabilities": capabilities,
        "upstreams": upstreams,
        "credentials_inspected": False,
        "provider_calls": 0,
        "upstream_code_executed": False,
        "scope": "Local runtime/files/Git HEAD and declared connections only. Missing upstreams or live connections are nonfatal. Full upstream integrity is checked by deps verify.",
    }


def command_doctor(as_json: bool) -> int:
    result = doctor_status()
    if as_json:
        _emit_json(result)
    else:
        print(f"Doctor: {result['status']}")
        for check in result["checks"]:
            print(f"  {check['status']}: {check['name']} — {check['detail']}")
        print("No credential values read; no provider calls or upstream code executed.")
    return 1 if result["status"] == "error" else 0


def _run_script(path: Path, arguments: Sequence[str] = ()) -> int:
    if not path.is_file():
        print(f"Required helper is not connected: {path}", file=sys.stderr)
        return 2
    try:
        # Project helper scripts only. Never run code inside an upstream checkout.
        return subprocess.run([sys.executable, str(path), *arguments], cwd=PROJECT_ROOT, check=False).returncode
    except OSError as error:
        print(f"Could not execute helper: {error}", file=sys.stderr)
        return 2


def command_score(input_value: str, output_value: str) -> int:
    input_path = _project_path(input_value)
    output_path = _project_path(output_value)
    if not input_path.is_file():
        print(f"Observation file does not exist: {input_path}", file=sys.stderr)
        return 2
    if input_path == output_path:
        print("Input and output must be different files.", file=sys.stderr)
        return 2
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return _run_script(AGENT_KIT / "score_observations.py", [str(input_path), str(output_path)])


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = stream.name
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        Path(temporary).replace(path)
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)


def command_run_offline() -> int:
    code = _run_script(AGENT_KIT / "validate_batch.py")
    qa: dict[str, Any] = {}
    if code == 0:
        qa = _load_json(AGENT_KIT / "qa-results.json")
    tasks = _task_summary()
    report = {
        "project": "Angry Miao SEO/GEO",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "execution_mode": "offline",
        "status": "passed" if code == 0 else "failed",
        "validation_exit_code": code,
        "validation": {
            key: qa[key]
            for key in (
                "status",
                "validated_at_utc",
                "checks_total",
                "fact_records",
                "operations",
                "question_count",
                "rollback_roundtrip",
            )
            if key in qa
        },
        "task_count": tasks["task_count"],
        "task_counts": tasks["counts"],
        "deployment_status": "not_deployed_by_this_run",
        "production_writes_performed": 0,
        "provider_calls_performed": 0,
        "upstream_code_executed": False,
        "live_geo_baseline_measured": False,
        "artifacts": {
            "tasks": "outputs/agent-kit/tasks.json",
            "qa_results": "outputs/agent-kit/qa-results.json",
            "status_report": "outputs/project-status.json",
        },
        "scope": "Replayed existing offline evidence and validation only. This run did not deploy a site, change Shopify, call paid APIs, run upstream projects, or measure real AI answers.",
    }
    target = PROJECT_ROOT / "outputs" / "project-status.json"
    _write_json_atomic(target, report)
    print(f"Offline {'validation passed' if code == 0 else 'validation failed'}; report: {target}")
    print("No deployment, storefront writes, provider calls, or live GEO measurements performed.")
    return code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="am-seo",
        description="Angry Miao SEO/GEO local project tools. No API keys needed for offline commands.",
        epilog="All project files and relative score paths resolve from the checkout, so the launcher works from any directory. No upstream code is imported or executed.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status", help="Read current task and capability declarations.")
    status.add_argument("--json", action="store_true", help="Print structured JSON.")
    doctor = commands.add_parser("doctor", help="Check local runtime, pinned checkouts and declared connections; never read credential values.")
    doctor.add_argument("--json", action="store_true", help="Print structured JSON.")
    commands.add_parser("validate", help="Replay the existing offline agent-kit validator; return its exit code.")
    score = commands.add_parser("score", help="Score an existing observations JSONL file; does not call a model or search API.")
    score.add_argument("observations", help="Input JSONL path (absolute or project-relative).")
    score.add_argument("output", nargs="?", default="outputs/geo-metrics.json", help="Output JSON path (default: outputs/geo-metrics.json; project-relative).")
    run = commands.add_parser("run", help="Run the offline validation and write outputs/project-status.json.")
    run.add_argument("--offline", action="store_true", required=True, help="Required: replay local artifacts only; never deploy or call providers.")
    deps = commands.add_parser("deps", help="Manage local pinned-upstream verification.")
    deps_commands = deps.add_subparsers(dest="deps_command", required=True)
    deps_commands.add_parser("verify", help="Run scripts/sync_upstreams.py verify offline; return its exit code.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "status":
            return command_status(args.json)
        if args.command == "doctor":
            return command_doctor(args.json)
        if args.command == "validate":
            return _run_script(AGENT_KIT / "validate_batch.py")
        if args.command == "score":
            return command_score(args.observations, args.output)
        if args.command == "run":
            return command_run_offline()
        if args.command == "deps" and args.deps_command == "verify":
            return _run_script(PROJECT_ROOT / "scripts" / "sync_upstreams.py", ["verify"])
    except (OSError, ValueError) as error:
        print(f"am-seo: {error}", file=sys.stderr)
        return 2
    return 2
