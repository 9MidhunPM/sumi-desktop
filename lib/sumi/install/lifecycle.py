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
        if layout.journal.exists():
            raise InstallError("An interrupted Sumi operation needs recovery. Run desktopctl restore pending before retrying.")
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


def _restore(layout: Layout, backup: Path, *, kind: str, dry_run: bool, expected_install: dict) -> dict:
    record = ownership.checked_snapshot(layout, backup)
    paths = [Path(path) for path in record["paths"]]
    if dry_run:
        return {"dry_run": True, "operation": kind, "snapshot": str(backup), "paths": [str(p) for p in paths]}
    with ownership.locked(layout):
        if ownership.recover_pending(layout):
            raise InstallError("Recovered an interrupted operation. Run rollback again to use the restored installation record.")
        if ownership.load(layout.manifest) != expected_install:
            raise InstallError("Installation ownership changed during rollback review. Retry the command.")
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
    return _restore(layout, Path(installed["rollback"]), kind="update-rollback", dry_run=dry_run, expected_install=installed)


def restore_previous(*, home: Path | None = None, dry_run: bool = False) -> dict:
    layout = Layout.from_environment(home)
    installed = _installed(layout)
    if not recovery_available(home=home):
        raise InstallError("No usable previous Hyprland desktop was backed up. Uninstall Sumi to remove its owned files.")
    groups: dict[Path, list[Path]] = {}
    for path in installed["artifacts"]:
        origin = Path(installed.get("origins", {}).get(path, installed["original"]))
        record = ownership.checked_snapshot(layout, origin)
        if path not in record["paths"]:
            raise InstallError(f"Missing original artifact backup for {path}; recovery stopped")
        groups.setdefault(origin, []).append(Path(path))
    result = {"operation": "previous-desktop", "snapshot": installed["original"],
              "paths": list(installed["artifacts"]), "dry_run": dry_run}
    if dry_run:
        return result
    with ownership.locked(layout):
        if ownership.recover_pending(layout):
            raise InstallError("Recovered an interrupted operation. Run original recovery again to use the restored installation record.")
        if ownership.load(layout.manifest) != installed:
            raise InstallError("Installation ownership changed during recovery review. Retry the command.")
        safety = ownership.snapshot(layout, [Path(path) for path in installed["artifacts"]], kind="previous-desktop-safety")
        ownership.json_write(layout.journal, {"version": 1, "snapshot": str(safety), "kind": "previous-desktop"})
        try:
            for backup, paths in groups.items():
                ownership.restore_snapshot(layout, backup, paths=paths, restore_manifest=False)
            original = ownership.checked_snapshot(layout, Path(installed["original"]))
            if original["previous_install"]:
                ownership.json_write(layout.manifest, original["previous_install"])
            else:
                layout.manifest.unlink()
            layout.journal.unlink()
            ownership.sync_directory(layout.records)
        except BaseException:
            ownership.recover_pending(layout)
            raise
    return {**result, "restored": True, "safety_snapshot": str(safety),
            "notes": _reload_user_units() + ["Log out and log in again to load the restored desktop."]}


def uninstall(*, home: Path | None = None, dry_run: bool = False) -> dict:
    layout = Layout.from_environment(home)
    installed = _installed(layout)
    unchanged, preserved = [], []
    for path, expected in installed["artifacts"].items():
        untouched = path not in installed.get("preserve_on_uninstall", []) and ownership.inventory(Path(path)) == expected
        (unchanged if untouched else preserved).append(Path(path))
    result = {"dry_run": dry_run, "removed_or_restored": [str(path) for path in unchanged],
              "preserved_edited": [str(path) for path in preserved], "backups": str(layout.records / "backups"),
              "user_data_preserved": True, "packages_removed": False}
    # Verify every required backup before making the first mutation.
    groups: dict[Path, list[Path]] = {}
    for path in unchanged:
        origin = Path(installed.get("origins", {}).get(str(path), installed["original"]))
        record = ownership.checked_snapshot(layout, origin)
        if str(path) not in record["paths"]:
            raise InstallError(f"Missing original artifact backup for {path}; uninstall stopped")
        groups.setdefault(origin, []).append(path)
    if dry_run:
        return result
    with ownership.locked(layout):
        if ownership.recover_pending(layout):
            raise InstallError("Recovered an interrupted operation. Re-run uninstall to review the restored ownership state.")
        if ownership.load(layout.manifest) != installed or any(
            ownership.inventory(path) != installed["artifacts"][str(path)] for path in unchanged
        ):
            raise InstallError("Installation files changed during uninstall review. Retry to preserve the new edits.")
        safety = ownership.snapshot(layout, unchanged, kind="uninstall-safety")
        ownership.json_write(layout.journal, {"version": 1, "snapshot": str(safety), "kind": "uninstall"})
        try:
            for backup, paths in groups.items():
                ownership.restore_snapshot(layout, backup, paths=paths, restore_manifest=False)
            ownership.json_write(layout.records / "last-uninstall.json", {**result, "safety_snapshot": str(safety)})
            layout.manifest.unlink()
            layout.journal.unlink()
            ownership.sync_directory(layout.records)
        except BaseException:
            ownership.recover_pending(layout)
            raise
    result["uninstalled"] = True
    result["notes"] = _reload_user_units() + ["Log out to stop the current Sumi session. Installed packages and system networking services were retained."]
    if preserved:
        result["notes"].append("Edited artifacts were preserved as whole files/directories. Review them and the backups before manual cleanup.")
    return result
