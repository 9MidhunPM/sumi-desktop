"""Bounded, private notification history for the shell's persistent center."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .statefiles import atomic_write, file_lock, state_path


def _entries(value: object) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError("Notification history must be a list")
    entries = []
    for item in value[:100]:
        if not isinstance(item, dict) or item.get("transient"):
            continue
        entry = {key: str(item.get(key, ""))[:limit] for key, limit in
                 (("appName", 256), ("summary", 1024), ("body", 16384), ("appIcon", 4096), ("time", 64))}
        original_id = item.get("originalId", item.get("id", 0))
        entry.update(originalId=original_id if isinstance(original_id, int) else 0,
                     unread=item.get("unread") is True, critical=item.get("critical") is True)
        # Native action objects and toast state only belong to the live server.
        entries.append(entry)
    return entries


def load(state_dir: Path | None = None) -> dict:
    directory = state_path(state_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    path = directory / "notifications.json"
    with file_lock(directory / "notifications.lock"):
        if not path.exists():
            return {"version": 1, "entries": []}
        os.chmod(path, 0o600)
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("Notification history has an invalid format")
        return {"version": 1, "entries": _entries(value.get("entries", []))}


def save(value: object, state_dir: Path | None = None) -> dict:
    directory = state_path(state_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    entries = _entries(value)
    with file_lock(directory / "notifications.lock"):
        atomic_write(directory / "notifications.json", (json.dumps({"version": 1, "entries": entries}) + "\n").encode(), 0o600)
    return {"saved": len(entries)}
