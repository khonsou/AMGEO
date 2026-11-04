"""Versioned planning inputs; reference claims never become measurement facts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_brand_context(root):
    root = Path(root).resolve()
    path = root / "config/brand-context.json"
    if not path.exists():
        return {"configured": False, "status": "not_configured", "version": None,
                "sha256": None, "integrity": {"verified": False, "errors": [], "files_verified": 0},
                "summary": {}, "context": None}
    errors, count, manifest = [], 0, {}
    raw = path.read_bytes()
    try:
        context = json.loads(raw)
        if not isinstance(context, dict) or not isinstance(context.get("version"), int) or isinstance(context.get("version"), bool) or context["version"] < 1:
            raise ValueError("Brand context requires a positive integer version")
        relative = context.get("source_manifest")
        if not isinstance(relative, str):
            raise ValueError("Brand context needs a source manifest")
        manifest_path = (root / relative).resolve()
        if not manifest_path.is_relative_to(root / "outputs/brand-context"):
            raise ValueError("Brand manifest path is outside the brand-context evidence directory")
        manifest = _read(manifest_path)
        if not isinstance(manifest, dict):
            raise ValueError("Brand source manifest must be an object")
        repository = manifest.get("repository", "")
        if not isinstance(repository, str) or not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("Brand source repository must be an official GitHub repository URL")
        commit = manifest.get("commit", "")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("Brand source commit must be an exact Git commit")
        files = manifest.get("files")
        if not isinstance(files, list) or len(files) != 5:
            raise ValueError("Brand source manifest requires exactly five reference files")
        names = set()
        for entry in files:
            local = (root / entry["local_path"]).resolve()
            if not local.is_relative_to(root / "outputs/brand-context/sources"):
                raise ValueError("Brand source path is outside the evidence sources directory")
            name = local.name
            if name in names:
                raise ValueError("Brand source filenames must be distinct")
            names.add(name)
            content = local.read_bytes()
            if hashlib.sha256(content).hexdigest() != entry.get("sha256"):
                raise ValueError(f"Brand source hash mismatch: {name}")
            if entry.get("source_url") != f"{repository}/blob/{commit}/{entry.get('path')}":
                raise ValueError(f"Brand source URL is not pinned to manifest commit: {name}")
            count += 1
        if names != {"brand.md", "audience.md", "methodology.md", "product.md", "visual.md"}:
            raise ValueError("Brand source references do not match the required five documents")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(str(exc))
        context = locals().get("context")
        if not isinstance(context, dict):
            context = {}
    if not isinstance(manifest, dict):
        manifest = {}
    personas = context.get("personas", [])
    config_sha = hashlib.sha256(raw).hexdigest()
    identity = {"config_sha256": config_sha, "repository": manifest.get("repository"),
                "commit": manifest.get("commit"), "source_commit_at": manifest.get("source_commit_at"),
                "files": [{key: entry.get(key) for key in ("path", "local_path", "source_url", "sha256", "bytes")}
                          for entry in manifest.get("files", []) if isinstance(entry, dict)]}
    context_sha = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"configured": True, "status": context.get("status", "invalid") if not errors else "integrity_error",
            "version": context.get("version"), "sha256": context_sha, "config_sha256": config_sha,
            "source_manifest": context.get("source_manifest"), "repository": manifest.get("repository"),
            "source_commit": manifest.get("commit"), "source_commit_at": manifest.get("source_commit_at"), "retrieved_at": manifest.get("retrieved_at"), "sources": deepcopy(manifest.get("files", [])),
            "integrity": {"verified": not errors, "errors": errors, "files_verified": count, "commit": manifest.get("commit")},
            "summary": {"positioning": deepcopy(context.get("positioning", {})),
                        "personas": [{key: p.get(key) for key in ("id", "name", "priority", "needs", "discovery", "content_angles")} for p in personas if isinstance(p, dict)],
                        "markets": deepcopy(context.get("markets", {})), "rules": deepcopy(context.get("rules", []))},
            "context": deepcopy(context)}


def context_status(cycle, current):
    used = cycle.get("brand_context_snapshot")
    if not used or not used.get("configured"):
        status, warning = "legacy_unversioned", "本轮未采用这套版本化品牌资料；请按新资料重新分析，历史记录保持原样。"
    elif used.get("sha256") != current.get("sha256") or not current.get("integrity", {}).get("verified"):
        status, warning = "stale", "本轮使用旧版品牌资料，建议重新分析；既有产物与执行记录不会被追认或覆盖。"
    else:
        status, warning = "current", ""
    return status, {"used_version": (used or {}).get("version"), "used_sha256": (used or {}).get("sha256"),
                    "current_version": current.get("version"), "current_sha256": current.get("sha256"), "warning": warning}
