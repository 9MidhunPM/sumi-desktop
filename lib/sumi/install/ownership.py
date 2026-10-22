"""Checksum snapshots and a durable journal for user-owned desktop artifacts.

Package transactions belong to pacman and are deliberately not reversed here.
No snapshot or deletion follows a symlink. The journal is durable before the
first destination is touched, so SIGKILL recovery does not rely on a trap.
"""
from __future__ import annotations

import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Iterator
import uuid

from .paths import InstallError, Layout


def load(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def write(path: Path, content: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".sumi-write-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def json_write(path: Path, value: dict) -> None:
    write(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def inventory(path: Path) -> dict | None:
    if not os.path.lexists(path):
        return None
    result = {}
    def visit(item: Path, name: str) -> None:
        info = item.lstat()
        value = {"mode": stat.S_IMODE(info.st_mode)}
        if stat.S_ISLNK(info.st_mode):
            value.update(type="link", target=os.readlink(item))
        elif stat.S_ISREG(info.st_mode):
            value.update(type="file", sha256=hashlib.sha256(item.read_bytes()).hexdigest())
        elif stat.S_ISDIR(info.st_mode):
            value.update(type="directory")
        else:
            raise InstallError(f"Refusing special file in managed artifacts: {item}")
        result[name] = value
        if value["type"] == "directory":
            for child in sorted(item.iterdir()):
                visit(child, str(Path(name) / child.name))
    visit(path, "")
    return result


def remove(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if source.is_symlink():
        destination.symlink_to(os.readlink(source))
    elif source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
    else:
        shutil.copy2(source, destination)


@contextlib.contextmanager
def locked(layout: Layout) -> Iterator[None]:
    layout.records.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(layout.records, 0o700)
    with (layout.records / "lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise InstallError("Another Sumi installation is running. Wait for it to finish.") from exc
        yield


def snapshot(layout: Layout, paths: list[Path], *, kind: str) -> Path:
    layout.validate(paths)
    identifier = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:10]
    destination = layout.records / "backups" / identifier
    destination.mkdir(parents=True, mode=0o700)
    records = {}
    for path in paths:
        record = {"inventory": inventory(path), "object": hashlib.sha256(str(path).encode()).hexdigest()}
        if record["inventory"] is not None:
            copy(path, destination / "objects" / record["object"])
            if inventory(destination / "objects" / record["object"]) != record["inventory"]:
                raise InstallError(f"Snapshot verification failed: {path}")
        records[str(path)] = record
    json_write(destination / "snapshot.json", {"version": 1, "kind": kind, "paths": records,
                                                "previous_install": load(layout.manifest)})
    sync_directory(destination)
    return destination


def checked_snapshot(layout: Layout, path: Path) -> dict:
    path = Path(path)
    if path.parent != layout.records / "backups" or path.is_symlink():
        raise InstallError("Recovery snapshot is outside the installation backup directory")
    record = load(path / "snapshot.json")
    if not record or record.get("version") != 1:
        raise InstallError(f"Recovery snapshot is missing or unsupported: {path}")
    layout.validate([Path(item) for item in record["paths"]])
    for item in record["paths"].values():
        object_id = item["object"]
        if len(object_id) != 64 or any(c not in "0123456789abcdef" for c in object_id):
            raise InstallError("Invalid backup object identifier")
        if item["inventory"] is not None and inventory(path / "objects" / object_id) != item["inventory"]:
            raise InstallError(f"Backup checksum mismatch: {path}. Restore from another backup.")
    return record


def replace(source: Path | None, destination: Path) -> None:
    """Stage beside the destination; a pending journal covers the rename gap."""
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = destination.parent / (".sumi-stage-" + uuid.uuid4().hex)
    try:
        if source is not None:
            copy(source, temporary)
        remove(destination)
        if source is not None:
            os.replace(temporary, destination)
        sync_directory(destination.parent)
    finally:
        remove(temporary)


def restore_snapshot(layout: Layout, backup: Path, *, paths: list[Path] | None = None,
                     restore_manifest: bool = True) -> dict:
    record = checked_snapshot(layout, backup)
    selected = [str(path) for path in paths] if paths is not None else list(record["paths"])
    if any(path not in record["paths"] for path in selected):
        raise InstallError("Requested recovery path is absent from the snapshot")
    for path in selected:
        item = record["paths"][path]
        replace(backup / "objects" / item["object"] if item["inventory"] is not None else None, Path(path))
    if restore_manifest:
        if record["previous_install"] is None:
            layout.manifest.unlink(missing_ok=True)
        else:
            json_write(layout.manifest, record["previous_install"])
    return record


def recover_pending(layout: Layout) -> bool:
    journal = load(layout.journal)
    if journal is None:
        return False
    restore_snapshot(layout, Path(journal["snapshot"]))
    layout.journal.unlink()
    sync_directory(layout.records)
    return True


def transact(layout: Layout, artifacts: dict[Path, Path], *, kind: str) -> dict:
    """Caller holds the lock and has staged all artifacts before entering."""
    previous = load(layout.manifest)
    paths = list(artifacts)
    layout.validate(paths)
    backup = snapshot(layout, paths, kind=kind)
    json_write(layout.journal, {"version": 1, "snapshot": str(backup), "kind": kind})
    try:
        for destination, staged in artifacts.items():
            replace(staged, destination)
        installed = {"version": 1, "installed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     "runtime": str(layout.runtime), "original": previous["original"] if previous else str(backup),
                     "rollback": str(backup) if previous else None,
                     "artifacts": {str(path): inventory(path) for path in paths},
                     "origins": dict(previous.get("origins", {})) if previous else {}}
        for path in paths:
            installed["origins"].setdefault(str(path), str(backup))
        # Keep ownership of an artifact removed from a newer release until uninstall.
        if previous:
            for path, value in previous["artifacts"].items():
                installed["artifacts"].setdefault(path, value)
        json_write(layout.manifest, installed)
        layout.journal.unlink()
        sync_directory(layout.records)
        return installed
    except BaseException:
        # This also handles Ctrl-C. SIGKILL leaves the same recoverable journal.
        recover_pending(layout)
        raise
