#!/usr/bin/env python3
"""Verify or restore the exact user-designated brand reference snapshot.

No upstream code is executed. A source update requires a reviewed new manifest
and context version; this command never follows moving main implicitly.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["verify", "restore"], default="verify", nargs="?")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "outputs/brand-context/source-manifest.json").read_text())
    commit = manifest["commit"]
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise ValueError("Reference manifest requires an exact Git commit")
    for item in manifest["files"]:
        path = (root / item["local_path"]).resolve()
        if not path.is_relative_to(root / "outputs/brand-context/sources"):
            raise ValueError("Reference path escapes source directory")
        if args.action == "restore":
            url = "https://raw.githubusercontent.com/khonsou/CyberboardR6MarketingPlan/" + commit + "/" + item["path"]
            request = urllib.request.Request(url, headers={"User-Agent": "AMSEO-brand-reference-restore"})
            with urllib.request.urlopen(request, timeout=40) as response:
                content = response.read(1024 * 1024)
            if hashlib.sha256(content).hexdigest() != item["sha256"]:
                raise ValueError("Downloaded reference hash mismatch: " + item["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_bytes(content)
            temporary.replace(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Reference hash mismatch: " + item["path"])
        print("[OK] " + item["path"])
    print("Pinned source: " + commit + "; no upstream code executed")


if __name__ == "__main__":
    main()
