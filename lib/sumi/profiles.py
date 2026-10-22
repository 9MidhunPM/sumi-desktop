"""Reversible desktop ownership and narrowly scoped, verified configuration snapshots.

The immutable original snapshot is never reused as a mutable profile. Switching
profiles first journals the current files and service state; a failed start rolls
back both. No application data, browser profiles, SSH material, or credentials are
part of the managed configuration set.
"""
from __future__ import annotations

from .paths import config_path, data_root, managed_path, allowed_path, canonical_path

import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
MANAGED_PATHS = (
    ".config/hypr/config/autostart.lua", ".config/hypr/config/keybinds.lua",
    ".config/hypr/config/theme.lua", ".config/hypr/config/general.lua", ".config/hypr/config/env.lua",
    ".config/hypr/hyprlock.conf", ".config/hypr/hypridle.conf",
    ".config/hypr/scripts/safe-logout.sh",
    ".config/hypr/hyprpaper.conf", ".config/hypr/scheme",
    ".config/quickshell", ".config/swaync", ".config/eww",
    ".config/rofi", ".config/wofi", ".config/kitty", ".config/ghostty",
    ".config/theme-switcher", ".config/waybar", ".config/dunst", ".config/Thunar/uca.xml",
    ".config/ghostty/config", ".config/ghostty/config.ghostty",
    ".config/gtk-3.0/settings.ini", ".config/gtk-3.0/gtk.css",
    ".config/gtk-4.0/settings.ini", ".config/qt6ct/qt6ct.conf",
    ".config/qt6ct/colors/Sumi.conf", ".config/kdeglobals",
    ".local/share/color-schemes/Sumi.colors", ".config/mimeapps.list",
    ".config/Antigravity/User/settings.json", ".config/Antigravity IDE/User/settings.json",
    ".config/Code/User/settings.json", ".config/nvim/init.lua", ".config/nvim/init.vim",
    ".local/share/applications/mimeapps.list", ".config/sumi/generated",
    ".local/share/dbus-1/services/org.erikreider.swaync.service",
    ".local/share/dbus-1/services/org.freedesktop.Notifications.service",
    ".config/systemd/user/swaync.service",
)
PRESENTATION_UNITS = ("sumi-shell.service", "swaync.service")
AUTHENTICATION_UNITS = ("plasma-polkit-agent.service",)
OBSERVED_UNITS = PRESENTATION_UNITS + AUTHENTICATION_UNITS + ("sumi-clipboard-text.service", "sumi-clipboard-image.service")
REQUIRED_PROGRAMS = ("qs", "hyprctl", "kitty", "thunar", "awww", "wpctl", "brightnessctl", "cliphist", "wl-paste", "hyprlock", "papers", "loupe", "satty", "hyprsunset", "qt6ct", "cava", "blueman-manager", "wf-recorder", "slurp")
PROFILE_SWITCH_START = "-- >>> SUMI PROFILE SWITCH START"
PROFILE_SWITCH_END = "-- <<< SUMI PROFILE SWITCH END"


class ProfileError(RuntimeError):
    """A profile operation could not complete safely."""


def home_path() -> Path:
    return Path(os.environ.get("SUMI_HOME", str(Path.home()))).expanduser()


def state_path(home: Path | None = None) -> Path:
    from .statefiles import state_path as location
    return location(home=home)


def data_path(home: Path | None = None) -> Path:
    from .statefiles import data_path as location
    return location(home=home)


def dry_mode() -> bool:
    return os.environ.get("SUMI_DRY_RUN", "") == "1"


def _stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def atomic_write(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def _json(path: Path, value: Any) -> None:
    atomic_write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _load(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def _run(argv: list[str], *, check: bool = True, timeout: float = 15, dry_run: bool = False) -> subprocess.CompletedProcess:
    if dry_run or dry_mode():
        return subprocess.CompletedProcess(argv, 0, "", "")
    try:
        result = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        if check:
            raise ProfileError(f"Could not run {shlex.join(argv)}: {exc}") from exc
        return subprocess.CompletedProcess(argv, 1, "", str(exc))
    if check and result.returncode:
        raise ProfileError(f"{shlex.join(argv)} failed: {(result.stderr or result.stdout).strip()}")
    return result


def _remove(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _safe_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ProfileError(f"Unsafe managed path: {value}")
    return path


def _inventory(path: Path) -> dict[str, dict[str, Any]]:
    """Inventory without following directory symlinks or opening special files."""
    entries: dict[str, dict[str, Any]] = {}

    def visit(item: Path, key: str) -> None:
        info = item.lstat()
        entry: dict[str, Any] = {"mode": stat.S_IMODE(info.st_mode)}
        if stat.S_ISLNK(info.st_mode):
            entry.update(type="symlink", target=os.readlink(item))
        elif stat.S_ISREG(info.st_mode):
            entry.update(type="file", sha256=hashlib.sha256(item.read_bytes()).hexdigest(), size=info.st_size)
        elif stat.S_ISDIR(info.st_mode):
            entry["type"] = "directory"
        else:
            raise ProfileError(f"Special file is outside snapshot scope: {item}")
        entries[key] = entry
        if entry["type"] == "directory":
            for child in sorted(item.iterdir()):
                visit(child, f"{key}/{child.name}" if key else child.name)

    visit(path, "")
    return entries


def _copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if source.is_symlink():
        destination.symlink_to(os.readlink(source), target_is_directory=source.is_dir())
    elif source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
    elif source.is_file():
        shutil.copy2(source, destination)
    else:
        raise ProfileError(f"Cannot snapshot special file: {source}")


def service_state(*, dry_run: bool = False) -> dict[str, dict[str, str]]:
    if dry_run or dry_mode():
        return {}
    result = {}
    for unit in OBSERVED_UNITS:
        enabled = _run(["systemctl", "--user", "is-enabled", unit], check=False).stdout.strip()
        active = _run(["systemctl", "--user", "is-active", unit], check=False).stdout.strip()
        result[unit] = {"enabled": enabled, "active": active}
    return result


def capture_snapshot(home: Path, destination: Path, *, paths: Iterable[str] = MANAGED_PATHS,
                     services: dict | None = None, immutable: bool = False,
                     external_dependencies: bool = True) -> dict:
    """Create one checksum-verified snapshot; destination must not exist.

    Missing destinations are recorded so restoring also removes files introduced
    by Sumi. External Quickshell module targets are archived independently while
    their original symlink identity is retained in the main snapshot.
    """
    home = Path(home).absolute()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination.exists():
        raise ProfileError(f"Snapshot already exists: {destination}")
    staging = Path(tempfile.mkdtemp(prefix=".snapshot-", dir=destination.parent))
    os.chmod(staging, 0o700)
    manifest = {"version": 1, "created": _stamp(), "home": str(home), "immutable": immutable,
                "roots": {"config": str(config_path(home)), "data": str(data_root(home))},
                "paths": {}, "dependencies": {}, "services": services or {}}
    try:
        pending = list(dict.fromkeys(paths))
        while pending:
            relative = pending.pop(0)
            if relative in manifest["paths"]:
                continue
            relative_path = _safe_relative(relative)
            source = managed_path(home, relative_path)
            physical = source.parent.resolve() / source.name
            if not allowed_path(home, physical):
                raise ProfileError(f"Managed file has a parent outside the home directory: {source}")
            location = canonical_path(home, physical)
            if not os.path.lexists(source):
                manifest["paths"][relative] = {"exists": False, "physical": location}
                continue
            inventory = _inventory(source)
            object_id = hashlib.sha256(relative.encode()).hexdigest()
            _copy(source, staging / "objects" / object_id)
            manifest["paths"][relative] = {"exists": True, "entries": inventory, "physical": location, "object": object_id}
            # Theme adapters update the resolved contents of file symlinks.
            # Archive that exact file too, preserving the link itself separately.
            for key, entry in inventory.items():
                if entry["type"] == "symlink":
                    resolved = (source / key if key else source).resolve()
                    if resolved.is_file() and allowed_path(home, resolved):
                        alias = canonical_path(home, resolved)
                        if alias not in manifest["paths"] and alias not in pending:
                            pending.append(alias)
            if relative == ".config/quickshell" and external_dependencies:
                for key, entry in inventory.items():
                    if entry["type"] != "symlink":
                        continue
                    link = source / key
                    resolved = link.resolve()
                    if not resolved.exists() or (key and resolved.is_relative_to(source.resolve())):
                        continue
                    dependency_id = hashlib.sha256(str(resolved).encode()).hexdigest()[:20]
                    if dependency_id not in manifest["dependencies"]:
                        _copy(resolved, staging / "dependencies" / dependency_id)
                        manifest["dependencies"][dependency_id] = {
                            "target": str(resolved), "link": str(link), "entries": _inventory(resolved)}
        _json(staging / "manifest.json", manifest)
        verify_snapshot(staging)
        os.rename(staging, destination)
        return manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def snapshot_object(snapshot: Path, relative: str, *, manifest: dict | None = None) -> Path:
    """Resolve one independent snapshot object without traversing saved links."""
    manifest = manifest or _load(Path(snapshot) / "manifest.json")
    if not manifest:
        raise ProfileError(f"Invalid snapshot: {snapshot}")
    entry = manifest["paths"].get(relative, {})
    object_id = entry.get("object")
    if object_id:
        if not re.fullmatch(r"[a-f0-9]{64}", object_id):
            raise ProfileError("Invalid snapshot object identifier")
        return Path(snapshot) / "objects" / object_id
    # Backwards-compatible reading of earlier snapshots. New captures always use
    # flat objects so an absolute saved directory symlink cannot redirect writes.
    return Path(snapshot) / "files" / _safe_relative(relative)


def verify_snapshot(snapshot: Path) -> dict:
    manifest = _load(Path(snapshot) / "manifest.json")
    if not manifest or manifest.get("version") != 1:
        raise ProfileError(f"Invalid snapshot: {snapshot}")
    for relative, entry in manifest["paths"].items():
        _safe_relative(relative)
        if entry["exists"] and _inventory(snapshot_object(Path(snapshot), relative, manifest=manifest)) != entry["entries"]:
            raise ProfileError(f"Snapshot checksum or metadata mismatch: {relative}")
    for dependency_id, entry in manifest.get("dependencies", {}).items():
        if not re.fullmatch(r"[a-f0-9]{20}", dependency_id):
            raise ProfileError("Invalid snapshot dependency identifier")
        if _inventory(Path(snapshot) / "dependencies" / dependency_id) != entry["entries"]:
            raise ProfileError(f"Snapshot dependency mismatch: {entry['target']}")
    return manifest


def restore_snapshot(snapshot: Path, home: Path, *, recover_dependencies: bool = False) -> dict:
    """Verify every byte before replacing destinations.

    Stable parent symlinks are supported; changed parent targets are rejected
    before any writes so restoration cannot be redirected to unrelated files.
    """
    snapshot, home = Path(snapshot), Path(home).absolute()
    manifest = verify_snapshot(snapshot)
    roots = manifest.get("roots")
    if roots and roots != {"config": str(config_path(home)), "data": str(data_root(home))}:
        raise ProfileError("XDG locations differ from the saved snapshot; restore with the original environment")
    resolved_targets = {}
    for relative, entry in manifest["paths"].items():
        logical = managed_path(home, _safe_relative(relative))
        expected = managed_path(home, _safe_relative(entry.get("physical", relative)))
        actual = logical.parent.resolve() / logical.name
        if actual != expected:
            raise ProfileError(f"Managed path has a changed symlink parent: {logical.parent}")
        resolved_targets[relative] = actual
    for relative, entry in manifest["paths"].items():
        target = resolved_targets[relative]
        _remove(target)
        if entry["exists"]:
            _copy(snapshot_object(snapshot, relative, manifest=manifest), target)
    if recover_dependencies:
        for dependency_id, entry in manifest.get("dependencies", {}).items():
            target = Path(entry["target"])
            # Existing project work always wins over an archived module tree.
            if not os.path.lexists(target):
                _copy(snapshot / "dependencies" / dependency_id, target)
    return manifest


@contextlib.contextmanager
def _operation_lock(state_dir: Path):
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state_dir, 0o700)
    with (state_dir / "operation.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ProfileError("Another desktop operation is already running") from exc
        yield


def in_shell_cgroup() -> bool:
    if os.environ.get("SUMI_CONTROLLER") == "1" or dry_mode():
        return False
    try:
        return any("sumi-shell.service" in line.split(":", 2)[-1].split("/")
                   for line in Path("/proc/self/cgroup").read_text().splitlines())
    except OSError:
        return False


def delegate_controller(argv: list[str], *, home: Path | None = None, state_dir: Path | None = None) -> dict:
    """Move a UI-requested transition outside the shell's lifetime and cgroup."""
    home, state_dir = home or home_path(), state_dir or state_path(home)
    from . import operations
    record = operations.create(argv, state_dir)
    unit = record["unit"].removesuffix(".service")
    command = ["systemd-run", "--user", "--collect", "--no-block", "--unit=" + unit,
               "--property=Type=exec", "--property=KillMode=process", "--setenv=SUMI_CONTROLLER=1",
               "--setenv=SUMI_HOME=" + str(home), "--setenv=SUMI_STATE_DIR=" + str(state_dir),
               "--setenv=SUMI_DATA_DIR=" + str(data_path(home))]
    for name in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_CURRENT_DESKTOP", "HYPRLAND_INSTANCE_SIGNATURE", "XDG_SESSION_ID"):
        if name in os.environ:
            command.append("--setenv=" + name + "=" + os.environ[name])
    command += ["--", str(ROOT / "bin/desktopctl"), "operation", "run", record["id"]]
    try:
        _run(command)
    except BaseException as exc:
        operations.update(record["id"], state_dir, status="failed", error=str(exc))
        raise
    return {**record, "scheduled": True, "log_command": "journalctl --user -u " + unit}


def profile_status(*, home: Path | None = None, state_dir: Path | None = None) -> dict:
    state_dir = state_dir or state_path(home)
    value = _load(state_dir / "profile.json", {"profile": "classic", "installed": False})
    value["original_backup"] = str((state_dir / "original").resolve()) if (state_dir / "original/manifest.json").exists() else None
    value["recovery_available"] = False
    if value.get("standalone"):
        from .installer import recovery_available
        value["recovery_available"] = recovery_available(home=home)
    elif value["original_backup"]:
        try:
            original = verify_snapshot(Path(value["original_backup"]))
            value["recovery_available"] = any(item.get("exists") for key, item in original["paths"].items() if key.startswith(".config/hypr/"))
        except (OSError, ValueError, RuntimeError):
            pass
    pending = _load(state_dir / "transaction.json")
    if pending:
        value["pending_recovery"] = pending
    return value


def ensure_original(home: Path, state_dir: Path, *, dry_run: bool = False) -> Path:
    original = state_dir / "original"
    if os.path.lexists(original):
        manifest = verify_snapshot(original)
        # Older immutable originals predate some integrations. Archive only
        # newly managed files once; never rewrite the user's original manifest.
        for relative in MANAGED_PATHS:
            if relative not in manifest["paths"]:
                addition = state_dir / "original-additions" / hashlib.sha256(relative.encode()).hexdigest()
                if not addition.exists():
                    capture_snapshot(home, addition, paths=(relative,), immutable=True)
                else:
                    verify_snapshot(addition)
        return original
    timestamped = state_dir / "backups" / ("original-" + _stamp())
    capture_snapshot(home, timestamped, paths=MANAGED_PATHS, services=service_state(dry_run=dry_run), immutable=True)
    _capture_desktop_state(timestamped, dry_run=dry_run)
    # A stable, atomic alias keeps recovery commands simple without hiding the
    # timestamped immutable backup's actual location.
    pointer = state_dir / (".original-" + str(os.getpid()))
    pointer.symlink_to(timestamped.relative_to(state_dir), target_is_directory=True)
    os.replace(pointer, original)
    return original


def _assert_unlocked(*, dry_run: bool = False) -> None:
    if dry_run or dry_mode():
        return
    # A TTY is a different login session. Select this user's actual graphical
    # session and recover its bus/display environment instead of checking the TTY.
    manager = _run(["systemctl", "--user", "show-environment"], check=False, timeout=3)
    allowed = {"DISPLAY", "WAYLAND_DISPLAY", "XDG_CURRENT_DESKTOP", "HYPRLAND_INSTANCE_SIGNATURE",
               "XDG_SESSION_ID", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR"}
    graphical_env = {}
    for line in manager.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep and key in allowed:
            graphical_env[key] = value
    sessions = _run(["loginctl", "list-sessions", "--no-legend"], check=False, timeout=3)
    candidates = [os.environ.get("XDG_SESSION_ID"), graphical_env.get("XDG_SESSION_ID")]
    candidates += [line.split()[0] for line in sessions.stdout.splitlines() if line.split()]
    selected = None
    for session in dict.fromkeys(item for item in candidates if item):
        result = _run(["loginctl", "show-session", session, "-p", "Type", "-p", "User", "-p", "Active", "-p", "LockedHint"],
                      check=False, timeout=3)
        properties = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        if result.returncode or properties.get("Type") not in {"wayland", "x11"} or properties.get("User") != str(os.getuid()):
            continue
        if selected is None or properties.get("Active") == "yes":
            selected = (session, properties)
        if properties.get("Active") == "yes":
            break
    if selected is None or selected[1].get("LockedHint") not in {"yes", "no"}:
        raise ProfileError("Cannot establish the graphical session lock state; ensure the Hyprland session is running")
    if selected[1]["LockedHint"] == "yes":
        raise ProfileError("Unlock the desktop before switching profiles")
    if _run(["pgrep", "-u", str(os.getuid()), "-x", "hyprlock"], check=False).returncode == 0:
        raise ProfileError("Hyprlock is active; unlock before switching profiles")
    from_tty = os.environ.get("XDG_SESSION_ID") != selected[0]
    for key, value in graphical_env.items():
        if key != "XDG_SESSION_ID" and (from_tty or not os.environ.get(key)):
            os.environ[key] = value
    os.environ["XDG_SESSION_ID"] = selected[0]


def shell_path(profile: str = "sumi", *, home: Path | None = None) -> Path:
    return ROOT / "shell" if profile == "sumi" else config_path(home or home_path()) / "quickshell"


def ipc(target: str, method: str, args: list[str] | None = None, *, home: Path | None = None,
        state_dir: Path | None = None, profile: str | None = None, dry_run: bool = False) -> str:
    active = profile or profile_status(home=home, state_dir=state_dir)["profile"]
    command = ["qs", "ipc", "-p", str(shell_path(active, home=home)), "call", target, method, *(args or [])]
    return _run(command, dry_run=dry_run).stdout.strip()


def _notifications_owned() -> bool:
    owner = _run(["busctl", "--user", "call", "org.freedesktop.DBus", "/org/freedesktop/DBus",
                  "org.freedesktop.DBus", "GetConnectionUnixProcessID", "s", "org.freedesktop.Notifications"],
                 check=False, timeout=2)
    process = _run(["systemctl", "--user", "show", "sumi-shell.service", "-p", "MainPID", "--value"],
                   check=False, timeout=2)
    match = re.fullmatch(r"u (\d+)\s*", owner.stdout)
    return bool(match and process.returncode == 0 and match.group(1) == process.stdout.strip() and match.group(1) != "0")


def _wait_ready(home: Path, state_dir: Path, *, dry_run: bool = False) -> None:
    if dry_run or dry_mode():
        return
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        command = ["qs", "ipc", "-p", str(shell_path()), "call", "sumi", "ping"]
        result = _run(command, check=False, timeout=2)
        if result.returncode == 0 and "pong" in result.stdout and _notifications_owned():
            return
        time.sleep(0.25)
    raise ProfileError("Sumi did not become ready with notification ownership within 15 seconds")


def _filter_autostart(original: str, executable: str) -> str:
    lines = []
    for line in original.splitlines():
        if "hl.exec_cmd" in line and re.search(r'["\'](?:/usr/bin/)?(?:qs|quickshell|eww|swaync)(?:[\s"\'])', line):
            lines.append("    -- Presentation is owned by desktopctl for the Sumi profile.")
        else:
            lines.append(line)
    lines += ["", 'hl.on("hyprland.start", function()', f"    hl.exec_cmd({json.dumps(shlex.quote(executable) + ' session-start')})", "end)", ""]
    return "\n".join(lines)


def _sumi_bindings(original: str, executable: str) -> str:
    from .hyprland import migrate_lua_commands
    from .shortcuts import render_bindings
    bindings, _ = render_bindings(original, executable)
    return migrate_lua_commands(bindings)


def _sumi_general(original: str, _executable: str = "") -> str:
    """Restore the original translucent applications without rewriting user tables."""
    start, end = "-- >>> SUMI SURFACES START", "-- <<< SUMI SURFACES END"
    if (original.count(start), original.count(end)) not in {(0, 0), (1, 1)}:
        raise ProfileError("Sumi surface markers are incomplete or duplicated")
    if start in original and original.index(end) < original.index(start):
        raise ProfileError("Sumi surface markers are out of order")
    result = re.sub(re.escape(start) + r".*?" + re.escape(end) + r"\s*", "", original, flags=re.S)
    overlay_rule = 'hl.layer_rule({ match = { namespace = "^sumi-overlay$" }, no_anim = true, blur = false })'
    overlay = ("-- Sumi panels animate their own content; keep the full-screen scrim inexpensive.\n"
               + overlay_rule + "\n\n") if overlay_rule not in result else ""
    # Opacity below one is necessary for visible blur behind opaque application
    # surfaces. Override only these defaults, preserving vibrancy, shadows,
    # rounding, fullscreen opacity and all other user decoration settings.
    block = (overlay + start + "\n"
             + "hl.config({ decoration = { active_opacity = 0.85, inactive_opacity = 0.8,\n"
             + "    blur = { enabled = true, size = 6, passes = 3 } } })\n" + end)
    # Keep the existing motion include last so its own idempotent updater does
    # not continually reorder this block and trigger an unnecessary reload.
    marker = "-- >>> SUMI MOTION START"
    if marker in result:
        position = result.index(marker)
        return result[:position].rstrip() + "\n\n" + block + "\n\n" + result[position:].rstrip() + "\n"
    return result.rstrip() + "\n\n" + block + "\n"


def _apply_sumi_surfaces(home: Path, *, dry_run: bool = False) -> bool:
    """Upgrade the current Sumi general file inside an already-held profile lock."""
    path = config_path(home) / "hypr/config/general.lua"
    previous = path.read_text() if path.exists() else None
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    updated = _sumi_general(previous or "")
    if updated == previous:
        return False
    try:
        atomic_write(path, updated, mode=mode)
        _refresh_desktop(dry_run=dry_run)
    except BaseException:
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            atomic_write(path, previous, mode=mode)
        _refresh_desktop(dry_run=dry_run)
        raise
    return True


def _profile_switch_bindings(original: str, home: Path) -> str:
    """Import shared controls without replacing either profile's own bindings."""
    start_count, end_count = original.count(PROFILE_SWITCH_START), original.count(PROFILE_SWITCH_END)
    if (start_count, end_count) not in {(0, 0), (1, 1)}:
        raise ProfileError("Shared profile shortcut markers are incomplete or duplicated")
    helper = config_path(home) / "sumi/shared/profile-switch.lua"
    snippet = (PROFILE_SWITCH_START + "\ndo\n"
               + "    local shared = loadfile(" + json.dumps(str(helper)) + ")\n"
               + "    if shared then shared() end\nend\n" + PROFILE_SWITCH_END)
    if start_count:
        start, end = original.index(PROFILE_SWITCH_START), original.index(PROFILE_SWITCH_END)
        if end < start:
            raise ProfileError("Shared profile shortcut markers are out of order")
        return original[:start] + snippet + original[end + len(PROFILE_SWITCH_END):]
    return original.rstrip("\n") + "\n\n" + snippet + "\n"


def _install_profile_switch(home: Path) -> None:
    """Keep the same switch shortcut and launcher available in both profiles.

    Shared files live outside profile-managed roots. Only a marked import is
    added to current bindings after restoration; archived snapshots stay intact.
    """
    bindings = config_path(home) / "hypr/config/keybinds.lua"
    original = bindings.read_text() if bindings.exists() else ""
    updated = _profile_switch_bindings(original, home)
    executable = home / ".local/bin/desktopctl"
    helper = config_path(home) / "sumi/shared/profile-switch.lua"
    helper_text = ('-- Shared by Classic and Sumi. Managed by desktopctl.\n'
                   + 'hl.bind("SUPER + CTRL + ALT + S", hl.dsp.exec_cmd('
                   + json.dumps(shlex.quote(str(executable)) + " profile toggle") + '))\n')
    # Desktop-entry string escaping precedes Exec argument parsing.
    argument = str(executable).replace("\\", "\\\\")
    for character in ('"', '`', '$'):
        argument = argument.replace(character, "\\" + character)
    argument = argument.replace("\\", "\\\\").replace("%", "%%")
    desktop = ('[Desktop Entry]\nType=Application\n'
               'Name=Switch desktop (Classic / Sumi)\n'
               'Comment=Switch between the Classic and Sumi desktop profiles\n'
               'Icon=preferences-desktop-theme\n'
               + 'Exec="' + argument + '" profile toggle\n'
               + 'Terminal=false\nCategories=Settings;DesktopSettings;\n'
               'Keywords=desktop;profile;classic;sumi;switch;\n')
    atomic_write(helper, helper_text, mode=0o644)
    atomic_write(data_root(home) / "applications/sumi-switch-desktop.desktop", desktop, mode=0o644)
    atomic_write(bindings, updated, mode=stat.S_IMODE(bindings.stat().st_mode) if bindings.exists() else 0o644)


def _generate_sumi(home: Path, baseline: Path, *, state_dir: Path | None = None) -> None:
    from . import hyprland, shortcuts
    state_dir = state_dir or state_path(home)
    executable = str(home / ".local/bin/desktopctl")
    manifest = verify_snapshot(baseline)
    def baseline_text(relative):
        if relative not in manifest["paths"]:
            # A profile captured before this integration existed still has the
            # untouched current file. The immutable addition covers recovery.
            path = managed_path(home, relative)
        else:
            path = snapshot_object(baseline, relative, manifest=manifest)
        return path.read_text() if path.exists() else ""
    # Read the selected Classic snapshot, never the currently generated loader.
    bindings = baseline_text(".config/hypr/config/keybinds.lua")
    _, helper = shortcuts.render_bindings(bindings, executable)
    atomic_write(config_path(home) / "sumi/generated/shortcuts.lua", helper, mode=0o644)
    for name, transform in (("autostart.lua", _filter_autostart), ("keybinds.lua", _sumi_bindings), ("general.lua", _sumi_general)):
        relative = f".config/hypr/config/{name}"
        result = transform(baseline_text(relative), executable)
        if name == "general.lua":
            result = hyprland.motion_include(result, home)
        path = managed_path(home, relative)
        mode = stat.S_IMODE(path.stat().st_mode) if name == "general.lua" and path.exists() else 0o644
        atomic_write(path, result, mode=mode)
    atomic_write(config_path(home) / "hypr/config/env.lua", hyprland.environment(baseline_text(".config/hypr/config/env.lua")), mode=0o644)
    for relative in (".config/hypr/hypridle.conf", ".config/hypr/scripts/safe-logout.sh"):
        original = baseline_text(relative)
        if original:
            mode = stat.S_IMODE((managed_path(home, relative)).stat().st_mode) if (managed_path(home, relative)).exists() else 0o644
            atomic_write(managed_path(home, relative), hyprland.migrate_shell_commands(original), mode=mode)
    motion = _load(state_dir / "motion.json", {}).get("mode", "normal")
    atomic_write(config_path(home) / "sumi/generated/motion.lua", hyprland.motion_lua(motion), mode=0o644)
    override = "[D-BUS Service]\nName=org.freedesktop.Notifications\nExec=/usr/bin/false\n"
    # The vendor uses a different basename for the same bus name; override both.
    for name in ("org.erikreider.swaync.service", "org.freedesktop.Notifications.service"):
        atomic_write(data_root(home) / "dbus-1/services" / name, override, mode=0o644)
    unit = config_path(home) / "systemd/user/swaync.service"
    _remove(unit)
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.symlink_to("/dev/null")


def _migrate_classic(home: Path) -> None:
    """Repair supported compositor integration without changing Classic visuals.

    Call only after capture/restore. Immutable archived source is never changed.
    """
    from . import hyprland
    executable = str(home / ".local/bin/desktopctl")
    transforms = {
        ".config/hypr/config/keybinds.lua": lambda text: hyprland.classic_bindings(text, executable),
        ".config/hypr/hypridle.conf": hyprland.migrate_shell_commands,
        ".config/hypr/scripts/safe-logout.sh": hyprland.migrate_shell_commands,
        ".config/quickshell/Workspaces.qml": hyprland.classic_workspace_qml,
        ".config/quickshell/Power.qml": lambda text: hyprland.classic_power_qml(text, executable),
    }
    for relative, transform in transforms.items():
        path = managed_path(home, relative)
        if path.exists():
            original = path.read_text()
            migrated = transform(original)
            if migrated != original:
                atomic_write(path, migrated, mode=stat.S_IMODE(path.stat().st_mode))


def _desktop_settings(*, dry_run: bool = False) -> dict[str, str]:
    keys = _run(["gsettings", "list-keys", "org.gnome.desktop.interface"], check=False, timeout=3, dry_run=dry_run)
    supported = set(keys.stdout.splitlines())
    settings = {}
    for key in ("color-scheme", "accent-color"):
        if key in supported:
            value = _run(["gsettings", "get", "org.gnome.desktop.interface", key], check=False, timeout=3, dry_run=dry_run)
            if value.returncode == 0:
                settings[key] = value.stdout.strip()
    return settings


def _apply_desktop_preferences(report: dict, *, dry_run: bool = False) -> None:
    if dry_run or dry_mode():
        return
    settings = _desktop_settings()
    if "color-scheme" in settings:
        _run(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "'prefer-dark'"])
    accent = report.get("theme", {}).get("colors", {}).get("accentBlue", "")
    if "accent-color" in settings and re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        palette = {"blue": "3584e4", "teal": "2190a4", "green": "3a944a", "yellow": "c88800",
                   "orange": "ed5b00", "red": "e62d42", "pink": "d56199", "purple": "9141ac", "slate": "6f8396"}
        rgb = tuple(int(accent[index:index + 2], 16) for index in (1, 3, 5))
        def distance(value):
            return sum((channel - int(value[index:index + 2], 16)) ** 2 for channel, index in zip(rgb, (0, 2, 4)))
        closest = min(palette, key=lambda name: distance(palette[name]))
        supported = _run(["gsettings", "range", "org.gnome.desktop.interface", "accent-color"], check=False).stdout
        if f"'{closest}'" in supported:
            _run(["gsettings", "set", "org.gnome.desktop.interface", "accent-color", repr(closest)])


def _capture_desktop_state(snapshot: Path, *, dry_run: bool = False) -> None:
    _capture_wallpaper(snapshot, dry_run=dry_run)
    _json(snapshot / "desktop-settings.json", _desktop_settings(dry_run=dry_run))
    manager = _run(["systemctl", "--user", "show-environment"], check=False, dry_run=dry_run)
    platform = next((line.partition("=")[2] for line in manager.stdout.splitlines()
                     if line.startswith("QT_QPA_PLATFORMTHEME=")), None)
    _json(snapshot / "platform-environment.json", {"QT_QPA_PLATFORMTHEME": platform})


def _restore_desktop_state(home: Path, snapshot: Path, *, dry_run: bool = False) -> None:
    platform = _load(snapshot / "platform-environment.json", {}).get("QT_QPA_PLATFORMTHEME")
    _set_platform_environment(platform, dry_run=dry_run)
    for key, value in _load(snapshot / "desktop-settings.json", {}).items():
        if key in {"color-scheme", "accent-color"}:
            _run(["gsettings", "set", "org.gnome.desktop.interface", key, value], dry_run=dry_run)
    _restore_wallpaper(home, snapshot, dry_run=dry_run)
    _reload_ghostty(dry_run=dry_run)


def _set_platform_environment(provider: str | None, *, dry_run: bool = False) -> None:
    """Keep compositor, user services and D-Bus application launches consistent."""
    assignment = "QT_QPA_PLATFORMTHEME=" + (provider or "")
    _run(["dbus-update-activation-environment", "--systemd", assignment], dry_run=dry_run)
    if provider is None:
        _run(["systemctl", "--user", "unset-environment", "QT_QPA_PLATFORMTHEME"], dry_run=dry_run)
    _run(["hyprctl", "eval", 'hl.env("QT_QPA_PLATFORMTHEME", ' + json.dumps(provider or "") + ')'], dry_run=dry_run)


def _thunar_actions(home: Path) -> None:
    path = config_path(home) / "Thunar/uca.xml"
    try:
        root = ET.fromstring(path.read_text()) if path.exists() else ET.Element("actions")
    except ET.ParseError as exc:
        raise ProfileError("Thunar custom actions XML is invalid; it was not overwritten") from exc
    if root.tag != "actions":
        raise ProfileError("Thunar custom actions file has an unfamiliar root")
    executable = shlex.quote(str(home / ".local/bin/desktopctl"))
    specs = (
        ("terminal", "Open in Kitty", "utilities-terminal", executable + " action terminal --working-directory=%f", True),
        ("project", "Open Project", "applications-development", executable + " action project %f", True),
        ("wallpaper", "Set Wallpaper", "preferences-desktop-wallpaper", executable + " action wallpaper %f", False),
    )
    for identifier, name, icon, command, directory in specs:
        unique = "sumi-" + identifier
        for old in list(root):
            if old.findtext("unique-id") == unique:
                root.remove(old)
        action = ET.SubElement(root, "action")
        for key, value in (("icon", icon), ("name", name), ("unique-id", unique), ("command", command),
                           ("description", name), ("patterns", "*")):
            ET.SubElement(action, key).text = value
        ET.SubElement(action, "directories" if directory else "image-files")
        ET.SubElement(action, "startup-notify")
    ET.indent(root)
    atomic_write(path, '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n", mode=0o644)


def _application_defaults(home: Path, *, dry_run: bool = False) -> None:
    choices = {
        "org.gnome.Papers.desktop": ("application/pdf",),
        "org.gnome.Loupe.desktop": ("image/png", "image/jpeg", "image/webp", "image/avif", "image/bmp", "image/gif", "image/tiff", "image/svg+xml"),
        "thunar.desktop": ("inode/directory",),
    }
    for desktop, mime_types in choices.items():
        command = ["env", f"XDG_CONFIG_HOME={config_path(home)}", f"XDG_DATA_HOME={data_root(home)}", "xdg-mime", "default", desktop, *mime_types]
        _run(command, dry_run=dry_run)


def _ghostty_ready_process(pid: int, *, proc_dir: Path, executable: Path) -> bool:
    process = proc_dir / str(pid)
    try:
        if process.stat().st_uid != os.getuid() or (process / "exe").resolve(strict=True) != executable:
            return False
        status = dict(line.split(":", 1) for line in (process / "status").read_text().splitlines() if ":" in line)
        caught = int(status.get("SigCgt", "0").strip(), 16)
        return bool(caught & (1 << (signal.SIGUSR2 - 1)))
    except (OSError, ValueError):
        return False


def _reload_ghostty(*, dry_run: bool = False, proc_dir: Path = Path("/proc")) -> dict:
    """Reload existing terminals without starting the broken vendor service.

    Ghostty 1.3.1's notify-reload unit races systemd's signal-handler validation.
    A ready direct GTK instance supports SIGUSR2 too. Verify that the handler is
    installed, open a stable pidfd, and verify identity again before signalling;
    startup and PID reuse therefore cannot deliver a fatal default signal.
    """
    report = {"reloaded": [], "warnings": []}
    if dry_run or dry_mode():
        return report
    program = shutil.which("ghostty")
    if not program:
        return report
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        report["warnings"].append("Existing Ghostty windows need Ctrl+Shift+, to reload; safe PIDFD signalling is unavailable.")
        return report
    executable = Path(program).resolve()
    try:
        candidates = [int(path.name) for path in proc_dir.iterdir() if path.name.isdigit()]
    except OSError as exc:
        report["warnings"].append(f"Could not inspect existing Ghostty processes: {exc}")
        return report
    for pid in candidates:
        if not _ghostty_ready_process(pid, proc_dir=proc_dir, executable=executable):
            continue
        descriptor = None
        try:
            descriptor = os.pidfd_open(pid, 0)
            if not _ghostty_ready_process(pid, proc_dir=proc_dir, executable=executable):
                continue
            signal.pidfd_send_signal(descriptor, signal.SIGUSR2, None, 0)
            report["reloaded"].append(pid)
        except ProcessLookupError:
            pass  # The window closed after enumeration; a new one loads config.
        except OSError as exc:
            report["warnings"].append(f"Could not reload Ghostty process {pid}: {exc}")
        finally:
            if descriptor is not None:
                os.close(descriptor)
    return report


def _apply_theme_effects(report: dict, *, dry_run: bool = False, state_dir: Path | None = None) -> None:
    # Prepare geometry before live effects, but publish only after the wallpaper
    # daemon has accepted the new image. The outer transaction owns rollback.
    scene = None
    if isinstance(report.get("theme"), dict) and report["theme"].get("wallpaper"):
        from .scenes import scene_for_theme
        scene = scene_for_theme(report["theme"])
    _apply_desktop_preferences(report, dry_run=dry_run)
    for command in report.get("reload_commands", []):
        if command == ["systemctl", "--user", "reload", "app-com.mitchellh.ghostty.service"]:
            terminal_reload = _reload_ghostty(dry_run=dry_run)
            report["terminal_reload"] = terminal_reload
            report.setdefault("warnings", []).extend(terminal_reload["warnings"])
            continue
        optional = command[:3] == ["systemctl", "--user", "reload"]
        _run(command, check=not optional, dry_run=dry_run)
    wallpaper = report.get("wallpaper")
    if wallpaper:
        # Callers pass their own state root; standalone/report-only use never
        # reads settings from the host user's unrelated desktop.
        try:
            settings = _load(state_dir / "settings.json", {}) if state_dir is not None else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            settings = {}
        if not isinstance(settings, dict):
            settings = {}
        reduced_motion = settings.get("reducedMotion", report.get("reducedMotion", False)) is True
        try:
            motion = _load(state_dir / "motion.json", {}) if state_dir is not None else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            motion = {}
        if not isinstance(motion, dict):
            motion = {}
        battery_motion = settings.get("fullMotion") is not True and motion.get("mode") == "battery"
        transition = (["--transition-type", "none"] if reduced_motion else
                      ["--transition-type", "grow", "--transition-duration", "0.18",
                       "--transition-fps", "30", "--transition-bezier", "0.16,1,0.3,1"] if battery_motion else
                      ["--transition-type", "grow", "--transition-duration", "0.65",
                       "--transition-fps", "60", "--transition-bezier", "0.16,1,0.3,1"])
        _run(["awww", "img", *transition, str(wallpaper)], dry_run=dry_run)
        if scene is not None and state_dir is not None:
            report["scene"] = scene
            if not dry_run:
                try:
                    previous_scene = _load(state_dir / "scene.json")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    previous_scene = None
                if previous_scene != scene:
                    _json(state_dir / "scene.json", scene)


def _prune_snapshots(state_dir: Path, *, keep: int = 5) -> dict:
    """Bound completed journals while retaining the snapshot needed for recovery.

    The immutable backups and mutable profile roots are deliberately outside the
    two transaction directories and are never traversed by this cleanup.
    """
    journal = _load(state_dir / "transaction.json", {})
    pending = Path(journal["snapshot"]).resolve() if journal.get("snapshot") else None
    removed, warnings = [], []
    for name in ("transactions", "theme-transactions"):
        directory = state_dir / name
        if not directory.is_dir() or directory.is_symlink():
            continue
        snapshots = sorted((item for item in directory.iterdir() if item.is_dir() and not item.is_symlink()
                            and not item.name.startswith(".") and (item / "manifest.json").is_file()),
                           key=lambda item: item.name, reverse=True)
        preserve = {item.resolve() for item in snapshots[:max(0, keep)]}
        if pending:
            preserve.add(pending)
        for snapshot in snapshots:
            if snapshot.resolve() in preserve:
                continue
            try:
                shutil.rmtree(snapshot)
                removed.append(str(snapshot))
            except OSError as exc:
                # Cleanup must never turn a successful desktop transition into a
                # rollback. Leaving an extra private backup is the safe outcome.
                warnings.append(str(exc))
    return {"removed": removed, "warnings": warnings}


def _record_variants(state_dir: Path, snapshot: Path) -> None:
    _json(snapshot / "variants.json", {item.name: item.read_text() for item in (state_dir / "themes").glob("*-custom.json")})


def _restore_variants(state_dir: Path, snapshot: Path) -> None:
    variants = _load(snapshot / "variants.json", {})
    for item in (state_dir / "themes").glob("*-custom.json"):
        if item.name not in variants:
            item.unlink()
    for name, text in variants.items():
        if re.fullmatch(r"[a-z0-9-]+-custom\.json", name):
            atomic_write(state_dir / "themes" / name, text)


def apply_theme_live(theme_id: str, *, home: Path | None = None, state_dir: Path | None = None,
                     dry_run: bool = False, accent: str | None = None) -> dict:
    """Apply owned files and live wallpaper as one recoverable operation."""
    home, state_dir = home or home_path(), state_dir or state_path(home)
    _assert_unlocked(dry_run=dry_run)
    with _operation_lock(state_dir):
        if _load(state_dir / "transaction.json"):
            raise ProfileError("Recover the interrupted profile switch before applying a theme")
        ensure_original(home, state_dir, dry_run=dry_run)
        rollback = state_dir / "theme-transactions" / _stamp()
        capture_snapshot(home, rollback, external_dependencies=False)
        _record_runtime(state_dir, rollback)
        _record_variants(state_dir, rollback)
        _capture_desktop_state(rollback, dry_run=dry_run)
        current = profile_status(home=home, state_dir=state_dir)
        _json(state_dir / "transaction.json", {"kind": "theme", "from": current["profile"], "to": current["profile"],
                                                "snapshot": str(rollback), "previous_state": current})
        try:
            from .themes import apply_theme, apply_custom_accent
            if accent is None:
                report = apply_theme(theme_id, home=home, state_dir=state_dir, dry_run=False)
            else:
                report = apply_custom_accent(theme_id, accent, home=home, state_dir=state_dir, dry_run=False)
            _apply_theme_effects(report, dry_run=dry_run, state_dir=state_dir)
            (state_dir / "transaction.json").unlink()
            _prune_snapshots(state_dir)
            return report
        except BaseException as exc:
            try:
                _restore_variants(state_dir, rollback)
                restore_snapshot(rollback, home)
                _restore_runtime(state_dir, rollback)
                _refresh_desktop(dry_run=dry_run)
                _restore_desktop_state(home, rollback, dry_run=dry_run)
                (state_dir / "transaction.json").unlink(missing_ok=True)
                _prune_snapshots(state_dir)
            except BaseException as recovery_exc:
                raise ProfileError(f"Theme failed ({exc}); recovery is pending ({recovery_exc}). Run desktopctl restore pending") from exc
            raise ProfileError(f"Theme failed; previous files and wallpaper restored: {exc}") from exc


def _service_restore(services: dict, *, dry_run: bool = False) -> None:
    _run(["systemctl", "--user", "daemon-reload"], dry_run=dry_run)
    for unit in PRESENTATION_UNITS:
        desired = services.get(unit, {})
        enabled = desired.get("enabled", "")
        if enabled.startswith("enabled"):
            _run(["systemctl", "--user", "enable", unit], check=False, dry_run=dry_run)
        elif enabled in {"disabled", "not-found", "", "static", "masked"}:
            _run(["systemctl", "--user", "disable", unit], check=False, dry_run=dry_run)
        if desired.get("active") == "active":
            _run(["systemctl", "--user", "start", unit], dry_run=dry_run)
        else:
            _run(["systemctl", "--user", "stop", unit], check=False, dry_run=dry_run)

    for unit in AUTHENTICATION_UNITS:
        desired = services.get(unit)
        if desired and desired.get("active") in {"active", "inactive"}:
            _run(["systemctl", "--user", "start" if desired["active"] == "active" else "stop", unit], dry_run=dry_run)


def _stop_sumi(*, dry_run: bool = False) -> None:
    _run(["systemctl", "--user", "stop", "sumi-shell.service"], check=False, dry_run=dry_run)
    _run(["systemctl", "--user", "disable", "sumi-shell.service"], check=False, dry_run=dry_run)
    _run(["qs", "kill", "-p", str(shell_path())], check=False, dry_run=dry_run)
    for unit in ("sumi-clipboard-text.service", "sumi-clipboard-image.service"):
        _run(["systemctl", "--user", "stop", unit], check=False, dry_run=dry_run)


def _start_sumi(home: Path, state_dir: Path, *, dry_run: bool = False) -> None:
    if profile_status(home=home, state_dir=state_dir).get("standalone"):
        from . import session
        session.start(home=home, state_dir=state_dir, dry_run=dry_run)
        _wait_ready(home, state_dir, dry_run=dry_run)
        return
    variables = [name for name in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_CURRENT_DESKTOP", "HYPRLAND_INSTANCE_SIGNATURE", "XDG_SESSION_ID")
                 if os.environ.get(name)]
    if variables:
        _run(["systemctl", "--user", "import-environment", *variables], dry_run=dry_run)
    _set_platform_environment("qt6ct", dry_run=dry_run)
    _run(["systemctl", "--user", "daemon-reload"], dry_run=dry_run)
    for unit in AUTHENTICATION_UNITS:
        _run(["systemctl", "--user", "start", unit], dry_run=dry_run)
    owning_service = _run(["systemctl", "--user", "is-active", "sumi-shell.service"], check=False, dry_run=dry_run)
    if owning_service.stdout.strip() not in {"active", "activating", "reloading"}:
        # A preview uses the same config path but has no persistent service owner.
        # Replace only this config's leftover process before qs --no-duplicate.
        _run(["qs", "kill", "-p", str(shell_path())], check=False, dry_run=dry_run)
    _run(["systemctl", "--user", "enable", "sumi-shell.service"], dry_run=dry_run)
    _run(["systemctl", "--user", "start", "sumi-shell.service"], dry_run=dry_run)
    _wait_ready(home, state_dir, dry_run=dry_run)
    from .actions import restore_clipboard_watchers
    restore_clipboard_watchers(state_dir=state_dir, dry_run=dry_run)


def _stop_classic(home: Path, *, dry_run: bool = False) -> None:
    _run(["qs", "kill", "-p", str(shell_path("classic", home=home))], check=False, dry_run=dry_run)
    _run(["eww", "--force-wayland", "--config", str(config_path(home) / "eww"), "kill"], check=False, dry_run=dry_run)
    _run(["systemctl", "--user", "stop", "swaync.service"], check=False, dry_run=dry_run)
    # Only SwayNC owns this executable name. No unrelated Quickshell instance is killed.
    _run(["pkill", "-x", "swaync"], check=False, dry_run=dry_run)


def _start_classic(home: Path, services: dict, *, dry_run: bool = False) -> None:
    _service_restore(services, dry_run=dry_run)
    if (config_path(home) / "quickshell/shell.qml").exists():
        _run(["qs", "-p", str(shell_path("classic", home=home)), "-n", "-d"], dry_run=dry_run)
    if (config_path(home) / "eww/eww.yuck").exists():
        _start_classic_eww(home, dry_run=dry_run)
    # Starting by the session bus restores whichever notification provider the
    # original configuration selected, including normal D-Bus autoactivation.
    _run(["busctl", "--user", "call", "org.freedesktop.DBus", "/org/freedesktop/DBus",
          "org.freedesktop.DBus", "StartServiceByName", "su", "org.freedesktop.Notifications", "0"], check=False, dry_run=dry_run)
    _wait_classic_ready(home, dry_run=dry_run)


def _start_classic_eww(home: Path, *, dry_run: bool = False) -> None:
    """Start the scoped daemon without pipes retained by its double fork."""
    if dry_run or dry_mode():
        return
    command = ["eww", "--force-wayland", "--config", str(config_path(home) / "eww")]
    log = state_path(home) / "classic-eww.log"
    log.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Eww 0.5 only redirects terminal descriptors when daemonizing. A captured
    # pipe stays open in the daemon forever, even after its launcher has exited.
    # A regular log file preserves diagnostics without waiting for pipe EOF.
    with log.open("ab") as output:
        os.chmod(log, 0o600)
        try:
            started = subprocess.run([*command, "--restart", "daemon"], stdin=subprocess.DEVNULL,
                                     stdout=output, stderr=subprocess.STDOUT, start_new_session=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProfileError(f"Could not start Classic Eww; see {log}: {exc}") from exc
    if started.returncode:
        raise ProfileError(f"Classic Eww daemon startup failed with exit {started.returncode}; see {log}")

    deadline = time.monotonic() + 15
    while (remaining := deadline - time.monotonic()) > 0:
        ping = _run([*command, "ping"], check=False, timeout=min(2, remaining))
        if ping.returncode == 0 and ping.stdout.strip() == "pong":
            break
        time.sleep(min(0.2, max(0, deadline - time.monotonic())))
    else:
        raise ProfileError(f"Classic Eww daemon did not answer ping within 15 seconds; see {log}")

    # No fallback daemon: if the verified daemon disappears, fail the profile
    # transaction instead of starting another daemon with captured descriptors.
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProfileError(f"Classic Eww startup timed out before opening clock_window; see {log}")
    _run([*command, "--no-daemonize", "open", "clock_window"], timeout=min(5, remaining))
    while (remaining := deadline - time.monotonic()) > 0:
        active = _run([*command, "active-windows"], check=False, timeout=min(2, remaining))
        if active.returncode == 0 and re.search(r"^clock_window:\s*clock_window\s*$", active.stdout, re.M):
            return
        time.sleep(min(0.2, max(0, deadline - time.monotonic())))
    raise ProfileError(f"Classic Eww did not show clock_window within 15 seconds; see {log}")


def _wait_classic_ready(home: Path, *, dry_run: bool = False) -> None:
    if dry_run or dry_mode():
        return
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        shell = _run(["qs", "ipc", "-p", str(shell_path("classic", home=home)), "show"], check=False, timeout=2)
        owner = _run(["busctl", "--user", "call", "org.freedesktop.DBus", "/org/freedesktop/DBus",
                      "org.freedesktop.DBus", "GetConnectionUnixProcessID", "s", "org.freedesktop.Notifications"],
                     check=False, timeout=2)
        if shell.returncode == 0 and re.search(r"\bbar\b", shell.stdout) and re.fullmatch(r"u [1-9]\d*\s*", owner.stdout):
            return
        time.sleep(0.25)
    raise ProfileError("Classic did not become ready with shell IPC and notification ownership within 15 seconds")


def _refresh_desktop(*, dry_run: bool = False) -> None:
    _run(["systemctl", "--user", "daemon-reload"], dry_run=dry_run)
    _run(["hyprctl", "reload"], dry_run=dry_run)
    errors = _run(["hyprctl", "configerrors"], dry_run=dry_run).stdout.strip()
    if errors:
        raise ProfileError("Hyprland rejected the generated configuration: " + errors)


def _record_runtime(state_dir: Path, snapshot: Path) -> None:
    runtime = {}
    for name in ("theme.json", "settings.json", "motion.json", "scene.json"):
        try:
            runtime[name] = _load(state_dir / name)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Derived motion/geometry can be recovered from normal defaults and
            # the saved theme. Invalid optional state must not block that repair.
            if name not in {"motion.json", "scene.json"}:
                raise
            runtime[name] = None
    _json(snapshot / "runtime.json", runtime)


def _restore_runtime(state_dir: Path, snapshot: Path) -> None:
    runtime = _load(snapshot / "runtime.json", {})
    for name, value in runtime.items():
        if name not in {"theme.json", "settings.json", "motion.json"}:
            continue
        if value is None:
            (state_dir / name).unlink(missing_ok=True)
        else:
            _json(state_dir / name, value)
    # Old snapshots predate scene.json. Reconstruct their image geometry rather
    # than leaving a newly committed scene attached to the restored wallpaper.
    # Publish last, after the theme and motion preferences are back in place.
    scene = runtime.get("scene.json")
    if scene is None:
        theme = runtime.get("theme.json")
        try:
            if (isinstance(theme, dict) and isinstance(theme.get("wallpaper"), str)
                    and Path(theme["wallpaper"]).is_file()):
                from .scenes import scene_for_theme
                from .themes import _catalog
                scene = scene_for_theme(theme, curated=_catalog()["themes"])
        except (OSError, ValueError, KeyError, TypeError):
            scene = None
    if scene is None:
        (state_dir / "scene.json").unlink(missing_ok=True)
    else:
        _json(state_dir / "scene.json", scene)


def _restore_wallpaper(home: Path, snapshot: Path, *, dry_run: bool = False) -> None:
    # Restore awww's per-output state captured at the transition rather than
    # guessing wallpaper names or changing monitor configuration.
    wallpaper = _load(snapshot / "wallpaper.json", {})
    for output, path in wallpaper.items():
        if Path(path).is_file():
            _run(["awww", "img", "--outputs", output, "--transition-type", "none", path], check=False, dry_run=dry_run)


def _capture_wallpaper(snapshot: Path, *, dry_run: bool = False) -> None:
    result = _run(["awww", "query"], check=False, dry_run=dry_run)
    wallpapers = {}
    for line in result.stdout.splitlines():
        match = re.match(r"([^:]+):.*?image:\s*(.+)$", line)
        if match:
            wallpapers[match.group(1).strip()] = match.group(2).strip()
    _json(snapshot / "wallpaper.json", wallpapers)


def install(*, home: Path | None = None, state_dir: Path | None = None,
            activate: bool = False, dry_run: bool = False) -> dict:
    home, state_dir = home or home_path(), state_dir or state_path(home)
    with _operation_lock(state_dir):
        original = ensure_original(home, state_dir, dry_run=dry_run)
        _capture_desktop_state(original, dry_run=dry_run) if not (original / "wallpaper.json").exists() else None
        executable = home / ".local/bin/desktopctl"
        atomic_write(executable, "#!/bin/sh\nexec " + shlex.quote(str(ROOT / "bin/desktopctl")) + ' "$@"\n', mode=0o755)
        unit_dir = config_path(home) / "systemd/user"
        for template in (ROOT / "systemd").glob("*.service"):
            content = template.read_text().replace("@DESKTOPCTL@", str(executable)).replace("@ROOT@", str(ROOT)).replace("@HOME@", str(home)).replace("@STATE@", str(state_dir)).replace("@DATA@", str(data_path(home)))
            atomic_write(unit_dir / template.name, content, mode=0o644)
        _install_profile_switch(home)
        if profile_status(home=home, state_dir=state_dir)["profile"] == "classic":
            _migrate_classic(home)
        _run(["systemctl", "--user", "daemon-reload"], dry_run=dry_run)
        current = profile_status(home=home, state_dir=state_dir)
        current.update(installed=True, install_root=str(ROOT))
        current.pop("pending_recovery", None)
        _json(state_dir / "profile.json", current)
    if activate:
        return use_profile("sumi", home=home, state_dir=state_dir, dry_run=dry_run)
    return profile_status(home=home, state_dir=state_dir)


def use_profile(profile: str, *, home: Path | None = None, state_dir: Path | None = None,
                dry_run: bool = False) -> dict:
    if profile not in {"sumi", "classic", "toggle"}:
        raise ProfileError(f"Unknown profile: {profile}")
    home, state_dir = home or home_path(), state_dir or state_path(home)
    _assert_unlocked(dry_run=dry_run)
    with _operation_lock(state_dir):
        current = profile_status(home=home, state_dir=state_dir)
        if current.get("standalone"):
            if profile == "sumi":
                _start_sumi(home, state_dir, dry_run=dry_run)
                return current
            raise ProfileError("Use desktopctl restore original to recover a verified previous desktop")
        if profile == "toggle":
            profile = "classic" if current["profile"] == "sumi" else "sumi"
        if current.get("pending_recovery"):
            raise ProfileError("An interrupted switch needs recovery: desktopctl restore pending")
        if not current.get("installed"):
            raise ProfileError("Run desktopctl install before switching profiles")
        if current["profile"] == profile:
            # Upgrades can add managed files absent from the immutable original.
            # Archive those bytes before either compatibility or shortcut edits.
            ensure_original(home, state_dir, dry_run=dry_run)
            _install_profile_switch(home)
            if profile == "classic":
                _migrate_classic(home)
            else:
                current["surfaces_changed"] = _apply_sumi_surfaces(home, dry_run=dry_run)
            return current
        original = ensure_original(home, state_dir, dry_run=dry_run)
        previous = current["profile"]
        transaction = state_dir / "transactions" / _stamp()
        services = service_state(dry_run=dry_run)
        capture_snapshot(home, transaction, services=services)
        _record_runtime(state_dir, transaction)
        _capture_desktop_state(transaction, dry_run=dry_run)
        saved = state_dir / "profiles" / previous
        if saved.exists():
            shutil.rmtree(saved)
        shutil.copytree(transaction, saved, symlinks=True)
        _json(state_dir / "transaction.json", {"from": previous, "to": profile,
                                                "snapshot": str(transaction), "previous_state": current})
        try:
            if previous == "sumi":
                _stop_sumi(dry_run=dry_run)
            else:
                _stop_classic(home, dry_run=dry_run)
            target_snapshot = state_dir / "profiles" / profile
            if target_snapshot.exists():
                restore_snapshot(target_snapshot, home)
                _restore_runtime(state_dir, target_snapshot)
            elif profile == "classic":
                restore_snapshot(original, home)
            if profile == "sumi":
                baseline = state_dir / "profiles/classic"
                _generate_sumi(home, baseline if baseline.exists() else original, state_dir=state_dir)
                _thunar_actions(home)
                _application_defaults(home, dry_run=dry_run)
                from .themes import apply_theme, DEFAULT_THEME_ID
                runtime = _load(state_dir / "theme.json", {})
                theme_id = runtime.get("id") or DEFAULT_THEME_ID
                report = apply_theme(theme_id, home=home, state_dir=state_dir, dry_run=False)
                _apply_theme_effects(report, dry_run=dry_run, state_dir=state_dir)
                _install_profile_switch(home)
                _refresh_desktop(dry_run=dry_run)
                _start_sumi(home, state_dir, dry_run=dry_run)
            else:
                _migrate_classic(home)
                _install_profile_switch(home)
                _refresh_desktop(dry_run=dry_run)
                metadata = verify_snapshot(target_snapshot if target_snapshot.exists() else original)
                _start_classic(home, metadata.get("services", {}), dry_run=dry_run)
                _restore_desktop_state(home, target_snapshot if target_snapshot.exists() else original, dry_run=dry_run)
            _json(state_dir / "profile.json", {"profile": profile, "installed": True,
                                               "install_root": str(ROOT), "changed": _stamp()})
            (state_dir / "transaction.json").unlink()
            _prune_snapshots(state_dir)
            return profile_status(home=home, state_dir=state_dir)
        except BaseException as exc:
            rollback_error = None
            try:
                _stop_sumi(dry_run=dry_run)
                _stop_classic(home, dry_run=dry_run)
                restore_snapshot(transaction, home)
                _restore_runtime(state_dir, transaction)
                if previous == "classic":
                    _migrate_classic(home)
                _install_profile_switch(home)
                _refresh_desktop(dry_run=dry_run)
                if previous == "sumi":
                    _start_sumi(home, state_dir, dry_run=dry_run)
                else:
                    _start_classic(home, services, dry_run=dry_run)
                _restore_desktop_state(home, transaction, dry_run=dry_run)
                _json(state_dir / "profile.json", {key: value for key, value in current.items() if key != "pending_recovery"})
                (state_dir / "transaction.json").unlink(missing_ok=True)
                _prune_snapshots(state_dir)
            except BaseException as recovery_exc:
                rollback_error = str(recovery_exc)
            if rollback_error:
                raise ProfileError(f"Switch failed ({exc}); recovery is pending ({rollback_error}). Run desktopctl restore pending") from exc
            raise ProfileError(f"Switch failed and {previous} was restored: {exc}") from exc


def restore_pending(*, home: Path | None = None, state_dir: Path | None = None, dry_run: bool = False) -> dict:
    home, state_dir = home or home_path(), state_dir or state_path(home)
    if (state_dir / "installer/pending.json").exists():
        from .installer import recover_pending
        return recover_pending(home=home, dry_run=dry_run)
    _assert_unlocked(dry_run=dry_run)
    with _operation_lock(state_dir):
        journal = _load(state_dir / "transaction.json")
        if not journal:
            raise ProfileError("There is no interrupted transition to restore")
        snapshot = Path(journal["snapshot"])
        kind = journal.get("kind", "profile")
        parent = state_dir / ("theme-transactions" if kind == "theme" else "transactions")
        if not snapshot.resolve().is_relative_to(parent.resolve()):
            raise ProfileError("Recovery snapshot is outside the transaction directory")
        metadata = verify_snapshot(snapshot)
        if kind == "theme":
            restore_snapshot(snapshot, home)
            _restore_runtime(state_dir, snapshot)
            _restore_variants(state_dir, snapshot)
            _install_profile_switch(home)
            _refresh_desktop(dry_run=dry_run)
            _restore_desktop_state(home, snapshot, dry_run=dry_run)
            _json(state_dir / "profile.json", journal["previous_state"])
            (state_dir / "transaction.json").unlink()
            _prune_snapshots(state_dir)
            return profile_status(home=home, state_dir=state_dir)
        _stop_sumi(dry_run=dry_run)
        _stop_classic(home, dry_run=dry_run)
        restore_snapshot(snapshot, home)
        _restore_runtime(state_dir, snapshot)
        if journal["from"] == "classic":
            _migrate_classic(home)
        _install_profile_switch(home)
        _refresh_desktop(dry_run=dry_run)
        if journal["from"] == "sumi":
            _start_sumi(home, state_dir, dry_run=dry_run)
        else:
            _start_classic(home, metadata.get("services", {}), dry_run=dry_run)
        _restore_desktop_state(home, snapshot, dry_run=dry_run)
        _json(state_dir / "profile.json", journal["previous_state"])
        (state_dir / "transaction.json").unlink()
        _prune_snapshots(state_dir)
        return profile_status(home=home, state_dir=state_dir)


def restore_original(*, home: Path | None = None, state_dir: Path | None = None, dry_run: bool = False) -> dict:
    home, state_dir = home or home_path(), state_dir or state_path(home)
    if profile_status(home=home, state_dir=state_dir).get("standalone"):
        from .installer import restore_previous
        return restore_previous(home=home, dry_run=dry_run)
    _assert_unlocked(dry_run=dry_run)
    with _operation_lock(state_dir):
        original = state_dir / "original"
        metadata = verify_snapshot(original)
        recovery = state_dir / "transactions" / _stamp()
        capture_snapshot(home, recovery, services=service_state(dry_run=dry_run))
        _record_runtime(state_dir, recovery)
        _capture_desktop_state(recovery, dry_run=dry_run)
        current = profile_status(home=home, state_dir=state_dir)
        _json(state_dir / "transaction.json", {"from": current["profile"], "to": "original",
                                                "snapshot": str(recovery), "previous_state": current})
        _stop_sumi(dry_run=dry_run)
        _stop_classic(home, dry_run=dry_run)
        restore_snapshot(original, home, recover_dependencies=True)
        for addition in sorted((state_dir / "original-additions").glob("*")):
            restore_snapshot(addition, home)
        _migrate_classic(home)
        _install_profile_switch(home)
        _refresh_desktop(dry_run=dry_run)
        _start_classic(home, metadata.get("services", {}), dry_run=dry_run)
        _restore_desktop_state(home, original, dry_run=dry_run)
        _json(state_dir / "profile.json", {"profile": "classic", "installed": True, "install_root": str(ROOT), "restored_original": _stamp()})
        (state_dir / "transaction.json").unlink(missing_ok=True)
        _prune_snapshots(state_dir)
        return profile_status(home=home, state_dir=state_dir)


def start(*, foreground: bool = False, home: Path | None = None, state_dir: Path | None = None,
          dry_run: bool = False) -> dict:
    home, state_dir = home or home_path(), state_dir or state_path(home)
    if foreground:
        command = ["qs", "-p", str(shell_path()), "-n"]
        if dry_run or dry_mode():
            return {"command": command}
        os.execvp(command[0], command)
    active = profile_status(home=home, state_dir=state_dir)["profile"]
    if active == "sumi":
        _start_sumi(home, state_dir, dry_run=dry_run)
    else:
        _start_classic(home, {}, dry_run=dry_run)
    return {"profile": active, "started": True}


def restart(*, home: Path | None = None, state_dir: Path | None = None, dry_run: bool = False) -> dict:
    home, state_dir = home or home_path(), state_dir or state_path(home)
    with _operation_lock(state_dir):
        current = profile_status(home=home, state_dir=state_dir)
        if current.get("pending_recovery"):
            raise ProfileError("An interrupted switch needs recovery: desktopctl restore pending")
        active = current["profile"]
        if active == "sumi":
            _stop_sumi(dry_run=dry_run)
            _start_sumi(home, state_dir, dry_run=dry_run)
        else:
            ensure_original(home, state_dir, dry_run=dry_run)
            _migrate_classic(home)
            _refresh_desktop(dry_run=dry_run)
            _run(["qs", "kill", "-p", str(shell_path("classic", home=home))], check=False, dry_run=dry_run)
            _run(["qs", "-p", str(shell_path("classic", home=home)), "-n", "-d"], dry_run=dry_run)
            _wait_classic_ready(home, dry_run=dry_run)
        return {"profile": active, "restarted": True}


def apply_motion(mode: str, *, home: Path | None = None, state_dir: Path | None = None,
                 dry_run: bool = False) -> dict:
    from .hyprland import motion_include, motion_lua
    content = motion_lua(mode)
    home, state_dir = home or home_path(), state_dir or state_path(home)
    with _operation_lock(state_dir):
        current = profile_status(home=home, state_dir=state_dir)
        if current.get("pending_recovery"):
            raise ProfileError("Recover the interrupted desktop transition before changing motion")
        if current["profile"] != "sumi":
            return {"mode": mode, "applied": False, "profile": current["profile"]}
        path = config_path(home) / "sumi/generated/motion.lua"
        previous = path.read_text() if path.exists() else None
        state_file = state_dir / "motion.json"
        previous_state = state_file.read_text() if state_file.exists() else None
        general = config_path(home) / "hypr/config/general.lua"
        previous_general = general.read_text() if general.exists() else None
        general_mode = stat.S_IMODE(general.stat().st_mode) if general.exists() else 0o644
        general_content = motion_include(previous_general or "", home)
        if previous == content and _load(state_file, {}).get("mode") == mode and previous_general == general_content:
            return {"mode": mode, "applied": True, "profile": "sumi", "changed": False}
        try:
            atomic_write(path, content, mode=0o644)
            _json(state_file, {"mode": mode})
            atomic_write(general, general_content, mode=general_mode)
            _refresh_desktop(dry_run=dry_run)
        except BaseException:
            for target, old, permissions in ((path, previous, 0o644), (state_file, previous_state, 0o600),
                                              (general, previous_general, general_mode)):
                if old is None:
                    target.unlink(missing_ok=True)
                else:
                    atomic_write(target, old, mode=permissions)
            _refresh_desktop(dry_run=dry_run)
            raise
        return {"mode": mode, "applied": True, "profile": "sumi", "changed": True}


def session_start(*, home: Path | None = None, state_dir: Path | None = None, dry_run: bool = False) -> dict:
    home, state_dir = home or home_path(), state_dir or state_path(home)
    if profile_status(home=home, state_dir=state_dir).get("standalone"):
        from . import session
        if _load(state_dir / "transaction.json"):
            restore_pending(home=home, state_dir=state_dir, dry_run=dry_run)
        return session.start(home=home, state_dir=state_dir, dry_run=dry_run)
    _run(["systemctl", "--user", "import-environment", "DISPLAY", "WAYLAND_DISPLAY", "XDG_CURRENT_DESKTOP", "HYPRLAND_INSTANCE_SIGNATURE", "XDG_SESSION_ID"], dry_run=dry_run)
    if _load(state_dir / "transaction.json"):
        return restore_pending(home=home, state_dir=state_dir, dry_run=dry_run)
    return start(home=home, state_dir=state_dir, dry_run=dry_run)


def doctor(*, home: Path | None = None, state_dir: Path | None = None, dry_run: bool = False) -> dict:
    home, state_dir = home or home_path(), state_dir or state_path(home)
    status = profile_status(home=home, state_dir=state_dir)
    checks = {program: bool(shutil.which(program)) for program in REQUIRED_PROGRAMS}
    original = status.get("original_backup")
    snapshot_error = None
    if original:
        try:
            verify_snapshot(Path(original))
            for addition in sorted((state_dir / "original-additions").glob("*")):
                verify_snapshot(addition)
        except (ProfileError, OSError) as exc:
            snapshot_error = str(exc)
    readiness = False if status.get("pending_recovery") else None
    if status["profile"] == "sumi" and not status.get("pending_recovery") and not (dry_run or dry_mode()):
        try:
            readiness = ipc("sumi", "ping", home=home, state_dir=state_dir) == "pong" and _notifications_owned()
        except ProfileError:
            readiness = False
    return {"profile": status, "programs": checks, "backup_verified": bool(original) and not snapshot_error,
            "backup_error": snapshot_error, "ready": readiness,
            "services": service_state(dry_run=dry_run), "shell": str(shell_path())}
