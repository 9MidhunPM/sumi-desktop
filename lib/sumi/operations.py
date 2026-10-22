"""Durable receipts for controllers that must outlive a shell restart."""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import io
import json
import os
from pathlib import Path
import re
import uuid


class NoOperationsError(LookupError):
    """There is no previous receipt to resume after shell startup."""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _path(state_dir: Path, operation_id: str) -> Path:
    if not isinstance(operation_id, str) or not re.fullmatch(r"[a-f0-9]{32}", operation_id):
        raise ValueError("Invalid operation ID")
    return Path(state_dir) / "operations" / (operation_id + ".json")


def create(command: list[str], state_dir: Path) -> dict:
    from .profiles import _json
    operation_id = uuid.uuid4().hex
    record = {"version": 1, "id": operation_id, "operation_id": operation_id,
              "status": "queued", "command": command, "created_at": _now(),
              "unit": "sumi-transition-" + operation_id + ".service"}
    record["updated_at"] = record["created_at"]
    _json(_path(state_dir, operation_id), record)
    _json(Path(state_dir) / "operations/latest.json", {"id": operation_id})
    return record


def update(operation_id: str, state_dir: Path, **changes) -> dict:
    from .profiles import _json
    record = status(operation_id, state_dir, reconcile=False)
    record.update(changes, updated_at=_now())
    _json(_path(state_dir, operation_id), record)
    return record


def status(operation_id: str, state_dir: Path, *, reconcile: bool = True) -> dict:
    from .profiles import _run, dry_mode
    if operation_id == "latest":
        try:
            latest = (Path(state_dir) / "operations/latest.json").read_text()
        except FileNotFoundError as exc:
            raise NoOperationsError("No desktop operations have been recorded.") from exc
        operation_id = json.loads(latest)["id"]
    record = json.loads(_path(state_dir, operation_id).read_text())
    if reconcile and record["status"] in {"queued", "running"} and not dry_mode():
        # A killed controller cannot write its own failure. Collected transient
        # units disappear; allow a startup grace period before treating that as
        # failure. A live controller owns the receipt lock while it runs.
        age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(record["updated_at"])).total_seconds()
        if age >= 30:
            with _path(state_dir, operation_id).with_suffix(".lock").open("a+") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return record
                # The controller may have completed or refreshed its receipt
                # between our first read and acquiring its lock. Reconcile the
                # current receipt, preserving completion and a renewed grace.
                record = status(operation_id, state_dir, reconcile=False)
                if record["status"] not in {"queued", "running"}:
                    return record
                age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(record["updated_at"])).total_seconds()
                if age < 30:
                    return record
                owner = _run(["systemctl", "--user", "show", record["unit"],
                              "-p", "ActiveState", "-p", "LoadState"], check=False, timeout=3)
                properties = dict(line.split("=", 1) for line in owner.stdout.splitlines() if "=" in line)
                if properties.get("ActiveState") in {"inactive", "failed"} or properties.get("LoadState") == "not-found":
                    record = update(operation_id, state_dir, status="failed",
                                    error="The desktop controller stopped before recording completion. Check desktopctl profile status for pending recovery.")
    return record


def run(operation_id: str, state_dir: Path, invoke) -> tuple[dict, int]:
    path = _path(state_dir, operation_id)
    with path.with_suffix(".lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("This desktop operation is already running") from exc
        record = status(operation_id, state_dir, reconcile=False)
        if record["status"] != "queued":
            raise RuntimeError("This desktop operation has already been started")
        update(operation_id, state_dir, status="running", pid=os.getpid())
        output, error = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                code = invoke(record["command"])
            try:
                result = json.loads(output.getvalue()) if output.getvalue().strip() else None
            except ValueError:
                result = {"message": output.getvalue().strip()}
            if code:
                record = update(operation_id, state_dir, status="failed", error=error.getvalue().strip() or "Desktop operation failed", exit_code=code)
            else:
                record = update(operation_id, state_dir, status="succeeded", result=result, exit_code=0)
            return record, code
        except BaseException as exc:
            update(operation_id, state_dir, status="failed", error=str(exc) or type(exc).__name__)
            raise
