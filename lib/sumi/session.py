"""Portable session rendering and lifecycle; importing this module has no effects."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = "sumi-session.target"
# Import only desktop environment keys, never the complete interactive environment.
ENVIRONMENT = (
    "DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS",
    "HYPRLAND_INSTANCE_SIGNATURE", "XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP",
    "XDG_SESSION_TYPE", "XDG_SESSION_ID", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
    "XDG_STATE_HOME", "XDG_CACHE_HOME", "PATH", "QT_QPA_PLATFORMTHEME",
    "SUMI_HOME", "SUMI_STATE_DIR", "SUMI_DATA_DIR",
)


def _literal(value: str | Path) -> str:
    """Lua accepts JSON string escapes for validated filesystem paths."""
    text = str(value)
    if any(ord(character) < 32 for character in text):
        raise ValueError("Sumi paths cannot contain control characters")
    return json.dumps(text, ensure_ascii=False)


def _unit_value(value: str | Path, *, command: bool = False) -> str:
    text = str(value)
    _literal(text)
    text = text.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    return text.replace("$", "$$") if command else text


def render_unit(template: str, values: dict[str, str | Path]) -> str:
    """Quote each substituted path according to the systemd directive grammar."""
    lines = []
    for line in template.splitlines():
        command = line.startswith("Exec")
        for key, value in values.items():
            line = line.replace("@" + key + "@", _unit_value(value, command=command))
        if re.search(r"@[A-Z_]+@", line):
            raise ValueError("Unresolved service template placeholder")
        lines.append(line)
    return "\n".join(lines) + "\n"


def build_artifacts(runtime: Path, config: Path, data: Path, state: Path,
                    bin_dir: Path, *, home: Path | None = None) -> dict[Path, tuple[bytes, int]]:
    """Render every session-owned artifact without creating directories or files.

    ``data`` and ``state`` are Sumi's directories, not the XDG parent directories.
    The controller always lives in the copied runtime, independently of PATH.
    """
    from .hyprland import motion_lua
    home = home or Path.home()
    paths = (runtime, config, data, state, bin_dir, home)
    for path in paths:
        if not path.is_absolute():
            raise ValueError("Session installation paths must be absolute")
        _literal(path)
    controller = runtime / "bin/desktopctl"
    shell_controller = shlex.quote(str(controller))
    lua = (ROOT / "templates/hyprland.lua").read_text()
    lua = lua.replace("@CONTROLLER_LUA@", _literal(shell_controller)).replace("@CONFIG_LUA@", _literal(config))
    # Fixed service commands avoid nesting shell paths inside Hyprlang syntax.
    idle = (ROOT / "templates/hypridle.conf").read_text()
    lock = "\n".join((
        "# Initial Sumi lock palette; theme selection replaces these visuals.",
        "$sumi_wallpaper = screenshot", "$sumi_main = rgba(e8eef5ff)",
        "$sumi_soft = rgba(c1cbd6ff)", "$sumi_accent = rgba(93b9dcff)",
        "$sumi_panel = rgba(161c24ee)", "$sumi_font = Noto Sans", "",
    )) + (ROOT / "templates/hyprlock.conf").read_text()
    artifacts = {
        config / "hypr/hyprland.lua": (lua.encode(), 0o644),
        config / "hypr/hypridle.conf": (idle.encode(), 0o644),
        config / "hypr/hyprlock.conf": (lock.encode(), 0o644),
        config / "hypr/config/general.lua": (("dofile(" + _literal(config / "sumi/generated/motion.lua") + ")\n").encode(), 0o644),
        config / "sumi/generated/motion.lua": (motion_lua("normal").encode(), 0o644),
        config / "xdg-desktop-portal/portals.conf": (b"[preferred]\ndefault=hyprland;gtk\norg.freedesktop.impl.portal.FileChooser=gtk\n", 0o644),
    }
    values = {"DESKTOPCTL": controller, "ROOT": runtime, "HOME": home,
              "CONFIG": config, "STATE": state, "DATA": data}
    for template in sorted((ROOT / "systemd").iterdir()):
        if template.suffix in {".service", ".target"}:
            artifacts[config / "systemd/user" / template.name] = (render_unit(template.read_text(), values).encode(), 0o644)
    return artifacts


def _run(argv: list[str], *, env: dict[str, str] | None = None, check: bool = True):
    result = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=30)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Command failed: " + shlex.join(argv))
    return result


def start(*, home: Path | None = None, state_dir: Path | None = None,
          dry_run: bool = False) -> dict:
    """Start only after the Wayland environment exists; never enable boot units."""
    home = home or Path(os.environ.get("SUMI_HOME", str(Path.home())))
    env = dict(os.environ)
    env.update(XDG_CURRENT_DESKTOP="Hyprland", XDG_SESSION_DESKTOP="Hyprland",
               XDG_SESSION_TYPE="wayland", QT_QPA_PLATFORMTHEME="qt6ct")
    env["PATH"] = str(home / ".local/bin") + os.pathsep + env.get("PATH", "/usr/local/bin:/usr/bin")
    keys = [key for key in ENVIRONMENT if env.get(key)]
    commands = [
        ["systemctl", "--user", "import-environment", *keys],
        ["dbus-update-activation-environment", "--systemd", *keys],
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "start", "pipewire.socket", "pipewire-pulse.socket", "wireplumber.service"],
        ["systemctl", "--user", "start", "xdg-desktop-portal-hyprland.service", "xdg-desktop-portal.service"],
        ["systemctl", "--user", "start", TARGET],
    ]
    if dry_run or env.get("SUMI_DRY_RUN") == "1":
        return {"started": False, "dry_run": True, "commands": commands}
    if not env.get("WAYLAND_DISPLAY") or not env.get("HYPRLAND_INSTANCE_SIGNATURE") or not env.get("XDG_RUNTIME_DIR"):
        raise RuntimeError("Start Sumi from a Hyprland session; WAYLAND_DISPLAY, HYPRLAND_INSTANCE_SIGNATURE and XDG_RUNTIME_DIR are required")
    for command in commands:
        _run(command, env=env)
    # Honor the persisted privacy choice; a shell restart never silently resumes.
    from .actions import restore_clipboard_watchers
    restore_clipboard_watchers(state_dir=state_dir)
    return {"profile": "sumi", "started": True, "target": TARGET}


def stop(*, dry_run: bool = False) -> dict:
    command = ["systemctl", "--user", "stop", TARGET]
    if not (dry_run or os.environ.get("SUMI_DRY_RUN") == "1"):
        _run(command)
    return {"stopped": not dry_run, "command": command}


def lock() -> dict:
    """The singleton unit prevents racing or duplicate lock screen processes."""
    _run(["systemctl", "--user", "start", "sumi-lock.service"])
    return {"lock_requested": True}


def suspend() -> dict:
    # Hypridle's lock-notify inhibitor, rather than a timing delay, protects sleep.
    active = _run(["systemctl", "--user", "is-active", "sumi-idle.service"], check=False)
    if active.returncode or active.stdout.strip() != "active":
        raise RuntimeError("Secure suspend needs Sumi's idle service. Run desktopctl session-start and retry")
    lock()
    _run(["systemctl", "suspend"])
    return {"suspend_requested": True}


def watch() -> dict:
    """Drain compositor events; stop scoped services on normal exit or a crash.

    This complements the shutdown Lua hook and works for TTY/display-manager
    launches without relying on a separately managed graphical-session.target.
    """
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    if not runtime or not signature or "/" in signature or signature in {".", ".."}:
        raise RuntimeError("A valid Hyprland runtime and instance are required")
    address = str(Path(runtime) / "hypr" / signature / ".socket2.sock")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.connect(address)
            while connection.recv(65536):
                pass
    finally:
        # --no-block avoids waiting for this watcher's own service to be stopped.
        _run(["systemctl", "--user", "--no-block", "stop", TARGET], check=False)
    return {"stopped": True, "target": TARGET}
