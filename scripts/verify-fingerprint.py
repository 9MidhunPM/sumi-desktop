#!/usr/bin/env python3
"""Run checks and record whether their source changed during parallel work.

Exit 0: checks passed and the source fingerprint stayed unchanged.
Exit 1: checks failed. Exit 2: checks passed but the source changed.
The JSON receipt and detailed log stay outside the source tree by default.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import time


SOURCE_DIRS = ("lib", "shell", "tests", "scripts", "templates", "systemd", "bin", "assets/themes")


def fingerprint(root: Path) -> dict:
    result = {}
    for directory in SOURCE_DIRS:
        for path in sorted((root / directory).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            try:
                data = path.read_bytes()
                modified = path.stat().st_mtime_ns
            except FileNotFoundError:
                continue
            result[str(path.relative_to(root))] = {"sha256": hashlib.sha256(data).hexdigest(), "mtime_ns": modified}
    return result


def digest(snapshot: dict) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, help="JSON result path; its sibling .log stores check output")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Optional argv after --; defaults to scripts/verify.sh")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    command = command or ["bash", "scripts/verify.sh"]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    receipt = (args.receipt or Path("/tmp") / f"sumi-verification-{stamp}.json").resolve()
    log = receipt.with_suffix(".log")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    before = fingerprint(root)
    started = time.monotonic()
    try:
        with log.open("w") as output:
            checks = subprocess.run(command, cwd=root, stdout=output, stderr=subprocess.STDOUT, check=False)
        exit_code = checks.returncode
    except OSError as error:
        log.write_text(str(error) + "\n")
        exit_code = 127
    after = fingerprint(root)
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    result = {
        "version": 1, "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "root": str(root), "command": command, "checks_exit_code": exit_code,
        "source_unchanged": not changed, "changed_files": changed,
        "before_sha256": digest(before), "after_sha256": digest(after),
        "source_files": len(after), "elapsed_seconds": round(time.monotonic() - started, 3),
        "log": str(log), "receipt": str(receipt),
    }
    receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if exit_code:
        print("\nLast check output:\n" + "\n".join(log.read_text().splitlines()[-18:]))
        return 1
    return 2 if changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
