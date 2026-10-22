"""Explicit official-repository package operations, never invoked for previews."""
from __future__ import annotations

import json
from pathlib import Path
import shlex
import subprocess

from .paths import InstallError


def manifest(source: Path) -> dict:
    return json.loads((source / "packaging/dependencies.json").read_text())


def package_command(source: Path) -> list[str]:
    packages = manifest(source)["packages"]
    if not packages or any(item["repository"] not in {"core", "extra"} for item in packages):
        raise InstallError("Only official Arch core/extra packages are supported")
    return ["sudo", "pacman", "-Syu", "--needed", "--"] + [
        item["repository"] + "/" + item["name"] for item in packages]


def install_packages(source: Path) -> None:
    command = package_command(source)
    print("Package operation (pacman will ask for confirmation):\n  " + shlex.join(command), flush=True)
    try:
        subprocess.run(command, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InstallError("Package installation failed. Desktop files were not changed. Fix the pacman/network error and rerun ./install.sh. Packages already installed by pacman are retained.") from exc


def configure_system_services() -> list[str]:
    """Start supported daemons without displacing another network manager."""
    notes = []
    def active(unit: str) -> bool:
        return subprocess.run(["systemctl", "is-active", "--quiet", unit], check=False).returncode == 0
    competing = any(active(unit) for unit in ("systemd-networkd.service", "connman.service"))
    units = [] if competing and not active("NetworkManager.service") else ["NetworkManager.service"]
    if not units:
        notes.append("Existing network manager retained. After migrating networking, run sudo systemctl enable --now NetworkManager.service to use Sumi network controls.")
    if Path("/sys/class/bluetooth").is_dir() and any(Path("/sys/class/bluetooth").iterdir()):
        units.append("bluetooth.service")
    else:
        notes.append("No Bluetooth adapter detected; Bluetooth service was not enabled.")
    if units:
        command = ["sudo", "systemctl", "enable", "--now", *units]
        print("System service operation:\n  " + shlex.join(command), flush=True)
        if subprocess.run(command, check=False).returncode:
            notes.append("A system service could not start; inspect sudo systemctl status " + " ".join(units))
    return notes
