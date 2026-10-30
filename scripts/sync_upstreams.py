#!/usr/bin/env python3
"""Verify or restore the project's pinned public GitHub checkouts.

Uses only Python's standard library and Git.  No upstream code, dependency
installer, submodule, or hook is run.  ``verify`` is strictly offline.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GITHUB_URL = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?$")
COMMIT = re.compile(r"[0-9a-f]{40}$")
NAME = re.compile(r"[a-z0-9][a-z0-9-]*$")


class UpstreamError(Exception):
    """An actionable error whose message contains no captured Git output."""


def git(path: Path | None, *args: str, network: bool = False) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    if not network:
        # A partial clone must not silently contact its promisor remote during
        # offline verification, including when inspecting a missing object.
        env["GIT_NO_LAZY_FETCH"] = "1"
    command = [
        "git", "-c", "credential.helper=", "-c", "core.hooksPath=/dev/null",
        "-c", "submodule.recurse=false", "-c", "protocol.file.allow=never",
        "-c", "protocol.ext.allow=never", *args,
    ]
    try:
        result = subprocess.run(
            command, cwd=path, env=env, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=300 if network else 60,
            check=False,
        )
    except FileNotFoundError as exc:
        raise UpstreamError("Git is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise UpstreamError(f"Git {args[0]} timed out; existing files were retained") from exc
    if result.returncode:
        # Git stderr can contain credential-bearing proxy URLs. Never echo it.
        raise UpstreamError(f"Git {args[0]} failed (exit {result.returncode}); inspect the repository locally")
    return result.stdout.strip()


def normalized_origin(url: str) -> str:
    return url.rstrip("/").removesuffix(".git").lower()


def safe_relative(value: Any, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise UpstreamError(f"Invalid {label}")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {".", ".."} for part in relative.parts):
        raise UpstreamError(f"Unsafe {label}")
    return relative


def checkout_path(root: Path, entry: dict[str, Any]) -> Path:
    relative = safe_relative(entry.get("path"), "checkout path")
    if len(relative.parts) != 2 or relative.parts[0] != "vendor":
        raise UpstreamError("Checkout paths must be direct children of vendor/")
    path = root.joinpath(*relative.parts)
    # Refuse links even when their destination happens to be within the root.
    for candidate in (root / "vendor", path):
        if candidate.is_symlink():
            raise UpstreamError("Symlinked checkout paths are not supported")
    if not path.resolve().is_relative_to((root / "vendor").resolve()):
        raise UpstreamError("Checkout path escapes vendor/")
    return path


def load_lock(lock_file: Path, root: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(lock_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UpstreamError("Cannot read a valid JSON upstream lock file") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise UpstreamError("Unsupported upstream lock schema")
    entries = data.get("upstreams")
    if not isinstance(entries, list) or not entries:
        raise UpstreamError("The lock must contain a nonempty upstreams list")
    names: set[str] = set()
    paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise UpstreamError("Invalid upstream entry")
        name = entry.get("name", "")
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in names:
            raise UpstreamError("Invalid or duplicate upstream name")
        url = entry.get("url", "")
        if not isinstance(url, str) or not GITHUB_URL.fullmatch(url):
            raise UpstreamError(f"{name}: only credential-free public GitHub HTTPS URLs are allowed")
        if not isinstance(entry.get("commit"), str) or not COMMIT.fullmatch(entry["commit"]):
            raise UpstreamError(f"{name}: commit must be a full lowercase 40-character SHA")
        if not isinstance(entry.get("default_branch"), str) or not entry["default_branch"]:
            raise UpstreamError(f"{name}: missing default_branch")
        path = checkout_path(root, entry)
        if str(path) in paths:
            raise UpstreamError("Duplicate upstream checkout path")
        safe_relative(entry.get("license_file"), "license path")
        names.add(name)
        paths.add(str(path))
    return entries


def inspect_repository(path: Path, entry: dict[str, Any]) -> tuple[str, bool]:
    if not path.is_dir() or not (path / ".git").exists():
        raise UpstreamError("Missing checkout; use sync to restore the pinned version")
    if Path(git(path, "rev-parse", "--show-toplevel")).resolve() != path.resolve():
        raise UpstreamError("Path is not the root of the expected checkout")
    origin = git(path, "remote", "get-url", "origin")
    if normalized_origin(origin) != normalized_origin(entry["url"]):
        raise UpstreamError("Existing origin differs from the lock; repository was retained")
    head = git(path, "rev-parse", "--verify", "HEAD")
    dirty = bool(git(path, "status", "--porcelain", "--untracked-files=all"))
    return head, dirty


def verify_entry(root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    path = checkout_path(root, entry)
    head, dirty = inspect_repository(path, entry)
    if dirty:
        raise UpstreamError("Checkout has local changes; files were retained")
    if head != entry["commit"]:
        raise UpstreamError("HEAD differs from the pinned commit; use sync after preserving local work")
    license_relative = safe_relative(entry["license_file"], "license path")
    license_file = path.joinpath(*license_relative.parts)
    if license_file.is_symlink() or not license_file.is_file():
        raise UpstreamError("Pinned license file is missing or symlinked")
    if not license_file.resolve().is_relative_to(path.resolve()):
        raise UpstreamError("License file escapes the checkout")
    return {"name": entry["name"], "status": "ok", "commit": head, "path": entry["path"]}


def sync_entry(root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    path = checkout_path(root, entry)
    if path.exists():
        head, dirty = inspect_repository(path, entry)
        if dirty:
            raise UpstreamError("Checkout has local changes; sync refused to modify or delete it")
        if head == entry["commit"]:
            return verify_entry(root, entry)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        # No checkout runs until the pinned object is available. If this fails,
        # leave the directory intact so no pre-existing work can be removed.
        git(None, "clone", "--no-checkout", "--depth=1", "--single-branch",
            "--filter=blob:none", "--no-tags", "--branch", entry["default_branch"],
            entry["url"], str(path), network=True)
    try:
        git(path, "cat-file", "-e", f"{entry['commit']}^{{commit}}")
    except UpstreamError:
        git(path, "fetch", "--no-tags", "--depth=1", "origin", entry["commit"], network=True)
    # A detach preserves existing branch refs. Never reset, clean, or delete.
    git(path, "checkout", "--detach", entry["commit"], network=True)
    return verify_entry(root, entry)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify", "sync"))
    parser.add_argument("--lock", type=Path, default=PROJECT_ROOT / "config" / "upstreams.lock.json")
    parser.add_argument("--name", action="append", help="Select a locked upstream; repeat to select several")
    parser.add_argument("--json", action="store_true", help="Print machine-readable results")
    args = parser.parse_args(argv)
    results: list[dict[str, Any]] = []
    try:
        entries = load_lock(args.lock, PROJECT_ROOT)
        if args.name:
            unknown = set(args.name) - {entry["name"] for entry in entries}
            if unknown:
                raise UpstreamError("Unknown upstream selection")
            entries = [entry for entry in entries if entry["name"] in args.name]
        for entry in entries:
            try:
                operation = verify_entry if args.action == "verify" else sync_entry
                results.append(operation(PROJECT_ROOT, entry))
            except UpstreamError as exc:
                results.append({"name": entry["name"], "status": "error", "message": str(exc)})
    except UpstreamError as exc:
        results.append({"name": "lock", "status": "error", "message": str(exc)})
    ok = bool(results) and all(result["status"] == "ok" for result in results)
    if args.json:
        print(json.dumps({"action": args.action, "ok": ok, "results": results}, ensure_ascii=False, indent=2))
    else:
        for result in results:
            detail = result.get("commit", result.get("message", ""))
            print(f"[{result['status'].upper()}] {result['name']}: {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
