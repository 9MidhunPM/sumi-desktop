"""Private, bounded desktop widget preferences and personal notes."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .statefiles import atomic_write, file_lock, state_path

MAX_STORAGE_BYTES = 262_144
WIDGET_NAMES = ("clock", "spotify", "priorities", "deadline")
LAYOUT_NAMES = ("left", "right", "split")


def defaults() -> dict:
    """Return fresh empty preferences; personal content never lives in the repo."""
    return {
        "version": 1,
        "enabled": {name: True for name in WIDGET_NAMES},
        "priorities": [{"text": "", "done": False} for _ in range(3)],
        "deadline": {"title": "", "at": None},
        "layouts": {},
    }


def _object(value: object, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{label} has an invalid format")
    return value


def _text(value: object, limit: int, label: str) -> str:
    if not isinstance(value, str) or len(value) > limit or "\0" in value:
        raise ValueError(f"{label} must be text of at most {limit} characters")
    return value


def normalize(value: object) -> dict:
    """Validate the complete document without dropping or truncating user data."""
    value = _object(value, {"version", "enabled", "priorities", "deadline", "layouts"}, "Widget settings")
    if type(value["version"]) is not int or value["version"] != 1:
        raise ValueError("Unsupported widget settings version")
    enabled = _object(value["enabled"], set(WIDGET_NAMES), "Enabled widgets")
    if any(type(enabled[name]) is not bool for name in WIDGET_NAMES):
        raise ValueError("Enabled widget values must be booleans")
    if not isinstance(value["priorities"], list) or len(value["priorities"]) != 3:
        raise ValueError("Widget priorities must contain exactly three tasks")
    priorities = []
    for item in value["priorities"]:
        item = _object(item, {"text", "done"}, "Widget priority")
        text = _text(item["text"], 180, "Priority text")
        if type(item["done"]) is not bool:
            raise ValueError("Priority completion must be a boolean")
        priorities.append({"text": text, "done": item["done"]})
    deadline = _object(value["deadline"], {"title", "at"}, "Widget deadline")
    title = _text(deadline["title"], 160, "Deadline title")
    at = deadline["at"]
    if at is not None:
        if (type(at) not in (int, float) or not 0 <= at <= 8_640_000_000_000_000
                or at != int(at)):
            raise ValueError("Deadline time must be epoch milliseconds or null")
        at = int(at)
    layouts = value["layouts"]
    if not isinstance(layouts, dict) or len(layouts) > 256:
        raise ValueError("Widget layouts must contain at most 256 image entries")
    for key, layout in layouts.items():
        if not _text(key, 512, "Layout image key") or layout not in LAYOUT_NAMES:
            raise ValueError("Widget layout must use a nonempty image key and left, right, or split")
    return {
        "version": 1,
        "enabled": dict(enabled),
        "priorities": priorities,
        "deadline": {"title": title, "at": at},
        "layouts": dict(layouts),
    }


def decode(payload: str | bytes) -> dict:
    """Use the same bounded parser for stdin and persisted state."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    if len(payload) > MAX_STORAGE_BYTES:
        raise ValueError("Widget settings exceed the storage limit")
    return normalize(json.loads(payload))


def _directory(state_dir: Path | None) -> Path:
    directory = state_path(state_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    return directory


def load(state_dir: Path | None = None) -> dict:
    directory = _directory(state_dir)
    path = directory / "widgets.json"
    with file_lock(directory / "widgets.lock"):
        if not path.exists():
            return defaults()
        os.chmod(path, 0o600)
        with path.open("rb") as handle:
            return decode(handle.read(MAX_STORAGE_BYTES + 1))


def save(value: object, state_dir: Path | None = None) -> dict:
    document = normalize(value)
    payload = (json.dumps(document, ensure_ascii=False) + "\n").encode("utf-8")
    if len(payload) > MAX_STORAGE_BYTES:
        raise ValueError("Widget settings exceed the storage limit")
    directory = _directory(state_dir)
    with file_lock(directory / "widgets.lock"):
        atomic_write(directory / "widgets.json", payload, 0o600)
    return {"saved": True, "version": 1}
