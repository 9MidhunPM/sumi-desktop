"""Read-only diagnostics with concrete recovery and setup instructions."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

from . import ownership, packages, prerequisites
from .paths import Layout


def diagnostics(*, home: Path | None = None) -> dict:
    layout = Layout.from_environment(home)
    source = Path(__file__).resolve().parents[3]
    checks = []
    def add(name, ok, fix, severity="error"):
        checks.append({"name": name, "ok": bool(ok), "severity": severity, "fix": "" if ok else fix})
    add("supported_host", not prerequisites.check_host(), "Use an installed Arch Linux x86_64 system with Python, sudo, and pacman, as a normal user.")
    installed = ownership.load(layout.manifest)
    add("installation", bool(installed), "Clone the public repository and run ./install.sh.")
    add("interrupted_operation", not layout.journal.exists(), "Run ./install.sh again (or --update for an installed desktop) to recover the pending file transaction.")
    for command, package in packages.manifest(source)["capabilities"]["required"].items():
        add("command:" + command, shutil.which(command), "Run sudo pacman -Syu --needed " + package)
    version_errors = prerequisites.check_versions()
    add("runtime_versions", not version_errors, " ".join(version_errors))
    if installed:
        for path, expected in installed["artifacts"].items():
            add("artifact:" + path, ownership.inventory(Path(path)) == expected,
                "This artifact differs from installation; updates back it up and uninstall preserves it. Use ./install.sh --update to regenerate defaults.", "info")
        try:
            ownership.checked_snapshot(layout, Path(installed["original"]))
            backup_ok = True
        except (OSError, ValueError, RuntimeError, KeyError):
            backup_ok = False
        add("original_backup", backup_ok, "The backup is missing or damaged. Preserve the current desktop and repair your backups before recovery/uninstall.")
    session = bool(os.environ.get("WAYLAND_DISPLAY") and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))
    add("hyprland_session", session, "Log out and select Hyprland, or start Hyprland from a TTY.", "info")
    if session:
        for unit in ("sumi-session.target", "sumi-shell.service", "sumi-awww.service", "sumi-idle.service"):
            try:
                status = subprocess.run(["systemctl", "--user", "is-active", "--quiet", unit], check=False,
                                        capture_output=True, timeout=10).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                status = False
            add("service:" + unit, status, "Run desktopctl session-start; inspect journalctl --user -b -u " + unit)
    hardware = {"battery": any(Path("/sys/class/power_supply").glob("BAT*")),
                "brightness": any(Path("/sys/class/backlight").glob("*")),
                "bluetooth": any(Path("/sys/class/bluetooth").glob("*"))}
    from .lifecycle import recovery_available
    return {"ok": all(check["ok"] for check in checks if check["severity"] == "error"),
            "checks": checks, "optional_hardware": hardware, "previous_desktop_available": recovery_available(home=home),
            "runtime": str(layout.runtime), "state": str(layout.state)}
