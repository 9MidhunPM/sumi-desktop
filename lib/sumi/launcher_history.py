"""Private, bounded memory of choices made successfully in the launcher."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import time

from .statefiles import atomic_write, file_lock, state_path

MAX_ENTRIES = 512
MAX_QUERIES = 32
MAX_QUERY_LENGTH = 120
MAX_REQUEST_BYTES = 4096
MAX_STORAGE_BYTES = 8_000_000
HALF_LIFE_SECONDS = 30 * 24 * 60 * 60
MAX_COUNT = 9_007_199_254_740_991
ACTION_IDS = frozenset(("appearance", "widgets", "settings", "notifications", "calendar",
                        "media", "pomodoro", "capture-region", "capture-annotate", "lock", "help", "power"))


def defaults() -> dict:
    return {"version": 1, "entries": {}}


def normalize_query(value: str) -> str:
    if not isinstance(value, str) or "\0" in value:
        raise ValueError("Launcher query must be text without null characters")
    return " ".join(value.lower().split())[:MAX_QUERY_LENGTH].rstrip()


def _identifier(value: object) -> str:
    if not isinstance(value, str) or len(value) > 512 or any(ord(c) < 32 for c in value) or "/" in value:
        raise ValueError("Invalid launcher entry identifier")
    if value.startswith("app:") and len(value) > 4:
        identifier = value.removesuffix(".desktop")
        if len(identifier) > 4:
            return identifier
    if value.startswith("action:") and value[7:] in ACTION_IDS:
        return value
    raise ValueError("Invalid launcher entry identifier")


def decode_request(payload: str) -> dict:
    if len(payload.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("Launcher history request exceeds the storage limit")
    try:
        value = json.loads(payload)
    except (ValueError, UnicodeError) as error:
        raise ValueError("Launcher history request is not valid JSON") from error
    if not isinstance(value, dict) or set(value) != {"id", "query"}:
        raise ValueError("Launcher history record requires an id and query")
    return {"id": _identifier(value["id"]), "query": normalize_query(value["query"])}


def _number(value: object) -> bool:
    return type(value) in (int, float) and 0 <= value <= MAX_COUNT and math.isfinite(value)


def _valid_stats(value: object, *, entry: bool = False) -> bool:
    fields = {"count", "score", "lastUsed"} | ({"queries"} if entry else set())
    return (isinstance(value, dict) and set(value) == fields
            and type(value["count"]) is int and 1 <= value["count"] <= MAX_COUNT
            and _number(value["score"]) and value["score"] <= value["count"]
            and _number(value["lastUsed"]))


def _validate(value: object) -> dict:
    if (not isinstance(value, dict) or set(value) != {"version", "entries"}
            or type(value["version"]) is not int or value["version"] != 1
            or not isinstance(value["entries"], dict) or len(value["entries"]) > MAX_ENTRIES):
        raise ValueError("Launcher history has an invalid format; reset learning to recover")
    for identifier, item in value["entries"].items():
        if _identifier(identifier) != identifier or not _valid_stats(item, entry=True):
            raise ValueError("Launcher history has an invalid entry; reset learning to recover")
        queries = item["queries"]
        if not isinstance(queries, dict) or len(queries) > MAX_QUERIES:
            raise ValueError("Launcher history has invalid queries; reset learning to recover")
        for query, stats in queries.items():
            if not query or normalize_query(query) != query or not _valid_stats(stats):
                raise ValueError("Launcher history has an invalid query; reset learning to recover")
    return value


def _directory(state_dir: Path | None) -> Path:
    directory = state_path(state_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    return directory


def _load(directory: Path) -> dict:
    path = directory / "launcher-history.json"
    if not path.exists():
        return defaults()
    os.chmod(path, 0o600)
    if path.stat().st_size > MAX_STORAGE_BYTES:
        raise ValueError("Launcher history exceeds the storage limit; reset learning to recover")
    try:
        return _validate(json.loads(path.read_text()))
    except (UnicodeError, ValueError) as error:
        raise ValueError("Launcher history could not be read; reset learning to recover") from error


def load(state_dir: Path | None = None) -> dict:
    directory = _directory(state_dir)
    with file_lock(directory / "launcher-history.lock"):
        return _load(directory)


def _save(directory: Path, document: dict) -> dict:
    payload = (json.dumps(document, ensure_ascii=False, allow_nan=False) + "\n").encode()
    if len(payload) > MAX_STORAGE_BYTES:
        raise ValueError("Launcher history exceeds the storage limit")
    atomic_write(directory / "launcher-history.json", payload, 0o600)
    return document


def _increment(previous: dict | None, now: float) -> dict:
    previous = previous or {"count": 0, "score": 0, "lastUsed": now}
    elapsed = max(0, now - previous["lastUsed"])
    score = previous["score"] * 2 ** (-elapsed / HALF_LIFE_SECONDS) + 1
    count = min(MAX_COUNT, previous["count"] + 1)
    return {"count": count, "score": min(score, count), "lastUsed": now}


def _prune(items: dict, limit: int, keep: str) -> None:
    oldest = sorted((key for key in items if key != keep), key=lambda key: (items[key]["lastUsed"], key))
    for key in oldest[:max(0, len(items) - limit)]:
        del items[key]


def record(value: dict, state_dir: Path | None = None, *, now: float | None = None) -> dict:
    if not isinstance(value, dict) or set(value) != {"id", "query"}:
        raise ValueError("Launcher history record requires an id and query")
    identifier, query = _identifier(value["id"]), normalize_query(value["query"])
    timestamp = time.time() if now is None else now
    if not _number(timestamp):
        raise ValueError("Invalid launcher history timestamp")
    directory = _directory(state_dir)
    with file_lock(directory / "launcher-history.lock"):
        document = _load(directory)
        previous = document["entries"].get(identifier)
        item = _increment(previous, timestamp)
        item["queries"] = previous["queries"] if previous else {}
        if query:
            item["queries"][query] = _increment(item["queries"].get(query), timestamp)
            _prune(item["queries"], MAX_QUERIES, query)
        document["entries"][identifier] = item
        _prune(document["entries"], MAX_ENTRIES, identifier)
        return _save(directory, document)


def reset(state_dir: Path | None = None) -> dict:
    directory = _directory(state_dir)
    with file_lock(directory / "launcher-history.lock"):
        # Reset deliberately repairs malformed history without having to read it.
        return _save(directory, defaults())
