"""Reversible update rollback and ownership-aware removal."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

from . import ownership
from .paths import InstallError, Layout


def _installed(layout: Layout) -> dict:
    value = ownership.load(layout.manifest)
    if not value:
        raise InstallError("No Sumi installation was found for this user.")
    layout.validate([Path(path) for path in value["artifacts"]])
    return value


def recovery_available(*, home: Path | None = None) -> bool:
    layout = Layout.from_environment(home)
    installed = ownership.load(layout.manifest)
    if not installed:
        return False
    try:
        original = ownership.checked_snapshot(layout, Path(installed["original"]))
        hypr = original["paths"].get(str(layout.config / "hypr"), {}).get("inventory") or {}
        return any(hypr.get(name, {}).get("type") == "file" for name in ("hyprland.lua", "hyprland.conf"))
    except (InstallError, OSError, ValueError, KeyError):
        return False


def _reload_user_units() -> list[str]:
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return ["Log in again to reload user service definitions."]
    try:
        result = subprocess.run(["systemctl", "--user", "daemon-reload"], check=False,
                                capture_output=True, text=True, timeout=15)
        if result.returncode:
            return ["Run systemctl --user daemon-reload after logging in again."]
    except (OSError, subprocess.TimeoutExpired):
        return ["Run systemctl --user daemon-reload after logging in again."]
    return []


def _restore(layout: Layout, backup: Path, *, kind: str, dry_run: bool) -> dict:
    record = ownership.checked_snapshot(layout, backup)
    paths = [Path(path) for path in record["paths"]]
    if dry_run:
        return {"dry_run": True, "operation": kind, "snapshot": str(backup), "paths": [str(p) for p in paths]}
    with ownership.locked(layout):
        ownership.recover_pending(layout)
        safety = ownership.snapshot(layout, paths, kind=kind + "-safety")
        ownership.json_write(layout.journal, {"version": 1, "snapshot": str(safety), "kind": kind})
        try:
            ownership.restore_snapshot(layout, backup)
            installed = ownership.load(layout.manifest)
            if installed:
                installed["rollback"] = str(safety)
                ownership.json_write(layout.manifest, installed)
            layout.journal.unlink()
            ownership.sync_directory(layout.records)
        except BaseException:
            ownership.recover_pending(layout)
            raise
    return {"restored": True, "operation": kind, "snapshot": str(backup), "safety_snapshot": str(safety),
            "notes": _reload_user_units() + ["Log out and log in again to load the restored desktop."]}


def rollback(*, home: Path | None = None, dry_run: bool = False) -> dict:
    layout = Layout.from_environment(home)
    installed = _installed(layout)
    if not installed.get("rollback"):
        raise InstallError("No update rollback snapshot exists yet. Use ./install.sh --update first.")
    return _restore(layout, Path(installed["rollback"]), kind="update-rollback", dry_run=dry_run)


def restore_previous(*, home: Path | None = None, dry_run: bool = False) -> dict:
    layout = Layout.from_environment(home)
    installed = _installed(layout)
    if not recovery_available(home=home):
        raise InstallError("No usable previous Hyprland desktop was backed up. Uninstall Sumi to remove its owned files.")
    return _restore(layout, Path(installed["original"]), kind="previous-desktop", dry_run=dry_run)

