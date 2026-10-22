"""Read-only host and dependency checks for supported Arch installations."""
from __future__ import annotations

import os
from pathlib import Path
import platform
import re
import shutil
import subprocess

from .paths import InstallError


def check_host(*, os_release: Path = Path("/etc/os-release"), machine: str | None = None,
               uid: int | None = None) -> list[str]:
    values = {}
    try:
        for line in os_release.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                values[key] = value.strip('"\'')
    except OSError as exc:
        raise InstallError(f"Cannot read {os_release}: {exc}") from exc
    errors = []
    if values.get("ID") != "arch":
        errors.append("This installer supports installed Arch Linux only (ID=arch).")
    if (machine or platform.machine()) != "x86_64":
        errors.append("This release supports x86_64 only.")
    if (os.getuid() if uid is None else uid) == 0:
        errors.append("Run ./install.sh as your normal desktop user, without sudo.")
    for command in ("python3", "pacman", "sudo", "systemctl"):
        if not shutil.which(command):
            errors.append(f"Missing prerequisite: {command}. Install it before continuing.")
    return errors


def check_versions() -> list[str]:
    errors = []
    for program, minimum in (("Hyprland", (0, 55, 0)), ("qs", (0, 3, 0))):
        try:
            result = subprocess.run([program, "--version"], text=True, capture_output=True, timeout=15)
            match = re.search(r"(?:v)?(\d+)\.(\d+)\.(\d+)", result.stdout + result.stderr)
            if result.returncode or not match or tuple(map(int, match.groups())) < minimum:
                errors.append(f"{program} must be at least {'.'.join(map(str, minimum))}; run a full Arch upgrade.")
        except (OSError, subprocess.TimeoutExpired):
            errors.append(f"Cannot query {program}; run ./install.sh to install its official package.")
    return errors
