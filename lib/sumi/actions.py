"""Small, argv-only desktop actions used by the Quickshell interface."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from .statefiles import atomic_write, file_lock, state_path

CLIPBOARD_UNITS = ("sumi-clipboard-text.service", "sumi-clipboard-image.service")


def run(argv: list[str], **kwargs):
    return subprocess.run(argv, check=True, **kwargs)


def spawn(argv: list[str], *, service_type: str = "exec", input_file: Path | None = None):
    if not shutil.which(argv[0]):
        raise RuntimeError(f"{argv[0]} is not installed")
    # A new process group does not leave the shell's systemd cgroup. Give each
    # application its own unit so restarting the desktop cannot terminate it.
    scoped = ["systemd-run", "--user", "--collect", "--quiet", f"--service-type={service_type}"]
    if input_file is not None:
        # systemd-run sends this as a literal StandardInputFile D-Bus property;
        # the manager handles unit-file escaping. Keep spaces and % unchanged.
        scoped.append("--property=StandardInput=file:" + str(input_file.resolve()))
    if service_type == "forking":
        scoped.append("--property=TimeoutStartSec=10s")
    for key in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "HYPRLAND_INSTANCE_SIGNATURE", "XDG_CURRENT_DESKTOP", "PATH"):
        if key in os.environ:
            scoped.append(f"--setenv={key}={os.environ[key]}")
    scoped += ["--", shutil.which(argv[0]) or argv[0], *argv[1:]]
    # Type=exec waits for execution; Type=forking waits for the initial process
    # to exit successfully and retains its daemon in the independent unit.
    run(scoped, capture_output=True, text=True, timeout=15)


def brightness_percent() -> int:
    output = run(["brightnessctl", "-m"], capture_output=True, text=True).stdout.strip()
    fields = output.split(",")
    if len(output.splitlines()) != 1 or len(fields) != 5 or not fields[3].endswith("%"):
        raise RuntimeError("Display brightness could not be read")
    try:
        percent = int(fields[3][:-1])
        current, maximum = int(fields[2]), int(fields[4])
    except ValueError as error:
        raise RuntimeError("Display brightness could not be read") from error
    if not 0 <= percent <= 100 or maximum <= 0 or not 0 <= current <= maximum:
        raise RuntimeError("Display brightness returned an invalid value")
    return percent


def night_light_state() -> dict:
    if not shutil.which("hyprsunset") or not shutil.which("hyprctl"):
        return {"available": False, "active": False, "temperature": None}
    result = subprocess.run(["hyprctl", "hyprsunset", "temperature"], capture_output=True, text=True, timeout=3)
    if result.returncode:
        process = subprocess.run(["pgrep", "-x", "hyprsunset"], capture_output=True, text=True, timeout=3)
        if process.returncode == 1:
            return {"available": True, "active": False, "temperature": None}
        raise RuntimeError("Night light is running but its current state could not be read")
    try:
        temperature = int(result.stdout.strip())
    except ValueError as error:
        raise RuntimeError("Night light returned an invalid temperature") from error
    if not 1000 <= temperature <= 20000:
        raise RuntimeError("Night light returned an invalid temperature")
    return {"available": True, "active": temperature < 6000, "temperature": temperature}


def toggle_night_light() -> dict:
    state = night_light_state()
    if not state["available"]:
        raise RuntimeError("Night light requires hyprsunset and hyprctl")
    active = not state["active"]
    temperature = "4200" if active else "6500"
    if state["temperature"] is None:
        spawn(["hyprsunset", "-t", temperature])
    else:
        run(["hyprctl", "hyprsunset", "temperature", temperature], capture_output=True, text=True, timeout=3)
    # A newly started daemon may take a moment to expose its IPC socket. Only
    # return a state observed from that socket, never an optimistic toggle.
    for attempt in range(20):
        try:
            observed = night_light_state()
            if observed["temperature"] is not None and observed["active"] == active:
                return observed
        except RuntimeError:
            pass
        if attempt < 19:
            time.sleep(0.1)
    raise RuntimeError("Night light did not confirm the requested state; try again")


def search_files(query: str, home: Path | None = None) -> list[dict]:
    """Bounded filename search; never follows symlinks or reads file contents."""
    home = home or Path.home()
    if len(query.strip()) < 2:
        return []
    ignored = {"node_modules", ".git", ".venv", "venv", "__pycache__", "build", "dist", ".next", "target", ".cache"}
    needle = query.casefold()
    results = []
    deadline = time.monotonic() + 1.0
    for folder in ("Downloads", "Documents", "Pictures", "Desktop", "Coading"):
        root = home / folder
        for parent, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in ignored)
            for name in dirs + sorted(files):
                if needle in name.casefold():
                    path = Path(parent) / name
                    results.append({"name": name, "path": str(path), "detail": str(path.relative_to(home)), "directory": name in dirs})
                    if len(results) >= 60:
                        return results
            if time.monotonic() >= deadline:
                return results
    return results


def _clipboard_paused(state_dir: Path | None = None) -> bool:
    try:
        preference = json.loads((state_path(state_dir) / "clipboard.json").read_text())
    except FileNotFoundError:
        return False
    except (OSError, ValueError) as error:
        raise RuntimeError("Clipboard preference could not be read; history was not resumed") from error
    if not isinstance(preference, dict) or not isinstance(preference.get("paused"), bool):
        raise RuntimeError("Clipboard preference is invalid; history was not resumed")
    return preference["paused"]


def _clipboard_observed_state(desired: bool) -> dict:
    """Read watcher state independently from the saved user preference."""
    states = []
    for unit in CLIPBOARD_UNITS:
        result = subprocess.run(["systemctl", "--user", "is-active", unit], capture_output=True, text=True, timeout=10)
        state = result.stdout.strip()
        if state not in {"active", "inactive", "failed", "activating", "deactivating", "reloading", "unknown"}:
            raise RuntimeError(result.stderr.strip() or "Clipboard watcher state is unavailable")
        states.append(state)
    active = [state in {"active", "activating", "reloading", "deactivating"} for state in states]
    return {"paused": not any(active), "desiredPaused": desired,
            "textActive": active[0], "imageActive": active[1],
            "healthy": all(state == ("inactive" if desired else "active") for state in states),
            "watchers": dict(zip(("text", "image"), states))}


def clipboard_state(state_dir: Path | None = None) -> dict:
    """Report both watchers; one inactive watcher does not mean capture is paused."""
    return _clipboard_observed_state(_clipboard_paused(state_dir))


def _set_clipboard_paused(paused: bool | None, state_dir: Path | None = None, *, persist: bool) -> dict:
    state_dir = state_path(state_dir)
    with file_lock(state_dir / "clipboard.lock", wait=False):
        if paused is None:
            paused = _clipboard_paused(state_dir)
        run(["systemctl", "--user", "stop" if paused else "start", *CLIPBOARD_UNITS], capture_output=True, text=True, timeout=15)
        # An explicit user choice can repair a malformed preference. Startup
        # still reads and validates it above before invoking any watcher command.
        result = _clipboard_observed_state(paused)
        expected = "inactive" if paused else "active"
        if not all(value == expected for value in result["watchers"].values()):
            raise RuntimeError("Clipboard watchers did not both " + ("stop" if paused else "start"))
        if persist:
            atomic_write(state_dir / "clipboard.json", (json.dumps({"version": 1, "paused": paused}) + "\n").encode())
        result.update(desiredPaused=paused, healthy=True)
        return result


def restore_clipboard_watchers(state_dir: Path | None = None, *, dry_run: bool = False) -> dict:
    """Restore the user's explicit pause preference when the shell starts."""
    if dry_run or os.environ.get("SUMI_DRY_RUN") == "1":
        return {"desiredPaused": _clipboard_paused(state_dir), "dry_run": True}
    return _set_clipboard_paused(None, state_dir, persist=False)


def clipboard(argv: list[str]):
    operation = argv[0] if argv else "list"
    if operation in {"pause", "resume", "status"}:
        result = clipboard_state() if operation == "status" else _set_clipboard_paused(operation == "pause", persist=True)
        print(json.dumps(result))
        return
    if not shutil.which("cliphist"):
        if operation == "list":
            print("[]")
            return
        raise RuntimeError("Clipboard history is not installed")
    if operation == "list":
        result = run(["cliphist", "list"], capture_output=True, text=True)
        entries = []
        for line in result.stdout.splitlines()[:100]:
            identifier, sep, preview = line.partition("\t")
            if sep and identifier.isdigit():
                entries.append({"id": identifier, "name": preview[:240], "detail": "Clipboard"})
        print(json.dumps(entries))
    elif operation == "clear":
        run(["cliphist", "wipe"])
    elif operation in {"copy", "delete"} and len(argv) > 1:
        identifier = argv[1]
        if not identifier.isdigit():
            raise ValueError("Invalid clipboard entry")
        if operation == "delete":
            run(["cliphist", "delete"], input=identifier.encode())
        else:
            decoded = run(["cliphist", "decode"], input=identifier.encode(), capture_output=True)
            run(["wl-copy"], input=decoded.stdout)
    else:
        raise ValueError("Unknown clipboard action")


def capture(argv: list[str]):
    mode = argv[0] if argv else "region"
    if mode not in {"region", "window", "output"}:
        raise ValueError("Unknown capture mode")
    destination = Path.home() / "Pictures" / "Screenshots"
    destination.mkdir(parents=True, exist_ok=True)
    annotate = "annotate" in argv
    if annotate and not shutil.which("satty"):
        raise RuntimeError("Satty is not installed")
    # Hyprshot can exit before its background grim process finishes. Reading
    # its raw pipe waits for that child's complete image; placing Hyprshot in
    # a Type=exec unit instead kills the child when the main script exits.
    capture_result = subprocess.run(["hyprshot", "-s", "-m", mode, "--raw"], capture_output=True)
    image = capture_result.stdout
    # Some packaged versions return 1 from picker cleanup after a valid PNG.
    if not image.startswith(b"\x89PNG\r\n\x1a\n") or not image.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82"):
        raise RuntimeError(capture_result.stderr.decode(errors="replace").strip() or "Screenshot cancelled")
    stamp = time.strftime("Screenshot-%Y%m%d-%H%M%S-") + str(time.time_ns() % 1_000_000_000) + ".png"
    output = destination / stamp
    if annotate:
        from .annotation import launch
        return launch(image, output, spawn)
    atomic_write(output, image)
    try:
        # wl-copy forks only after setting the Wayland selection. A forking
        # unit both acknowledges copy success and keeps its owner alive after
        # this controller exits or the desktop shell restarts.
        spawn(["wl-copy", "--type", "image/png"], service_type="forking", input_file=output)
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"Screenshot saved to {output}, but clipboard copy failed: {error}") from error
    if shutil.which("notify-send"):
        # Notification delivery is optional; it must not undo a saved copy.
        try:
            run(["notify-send", "--app-name=Sumi", "--icon=camera-photo", "Screenshot saved", "Saved to Pictures/Screenshots and copied to the clipboard"], capture_output=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass
    return {"file": str(output), "saved": True, "copied": True}


def _recorder_running(data: dict) -> bool:
    try:
        cmdline = Path(f"/proc/{int(data['pid'])}/cmdline").read_bytes().split(b"\0")
        return bool(cmdline[0]) and Path(os.fsdecode(cmdline[0])).name == "wf-recorder" and os.fsencode(data["file"]) in cmdline
    except (OSError, KeyError, TypeError, ValueError):
        return False


def recording(operation: str):
    """Serialize selection/start/stop, and track only this desktop's recorder."""
    if operation not in {"start", "stop", "status"}:
        raise ValueError("Unknown recording operation")
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "sumi"
    runtime.mkdir(mode=0o700, exist_ok=True)
    pidfile = runtime / "recorder.json"
    with file_lock(runtime / "recorder.lock", wait=False):
        try:
            data = json.loads(pidfile.read_text())
        except (FileNotFoundError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        active = _recorder_running(data)
        if operation == "status":
            return {"recording": active, "file": data.get("file") if active else None}
        if operation == "stop":
            if active:
                try:
                    os.kill(int(data["pid"]), signal.SIGINT)
                except ProcessLookupError:
                    pass
                deadline = time.monotonic() + 5
                while _recorder_running(data):
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Recording is still finishing; its tracking was retained. Try Stop again")
                    time.sleep(0.05)
            pidfile.unlink(missing_ok=True)
            return {"recording": False, "file": data.get("file")}
        if active:
            raise RuntimeError("A Sumi recording is already running")
        pidfile.unlink(missing_ok=True)
        geometry = run(["slurp"], capture_output=True, text=True).stdout.strip()
        if not geometry:
            return {"recording": False, "cancelled": True}
        destination = Path.home() / "Videos" / "Recordings"
        destination.mkdir(parents=True, exist_ok=True)
        filename = destination / (time.strftime("Recording-%Y%m%d-%H%M%S-") + str(time.time_ns() % 1_000_000_000) + ".mp4")
        error_log = runtime / "recorder-error.log"
        atomic_write(error_log, b"")
        process = None
        interrupted = None
        cleaning = False
        previous_handlers = {}

        def interrupt_startup(signum, _frame):
            nonlocal interrupted
            interrupted = signum
            # A signal inside Popen must not interrupt assignment of its child
            # handle. Once that handle exists the outer guard can clean it up.
            if process is not None and not cleaning:
                raise SystemExit(128 + signum)

        try:
            for signum in (signal.SIGTERM, signal.SIGINT):
                previous_handlers[signum] = signal.signal(signum, interrupt_startup)
            if interrupted is not None:
                raise SystemExit(128 + interrupted)
            with error_log.open("wb") as errors:
                process = subprocess.Popen(["wf-recorder", "-g", geometry, "-f", str(filename)], start_new_session=True,
                                           stdout=subprocess.DEVNULL, stderr=errors)
            data = {"pid": process.pid, "file": str(filename)}
            # Publish ownership before any readiness delay. A controller killed
            # after this point leaves a recorder that status/stop can identify.
            atomic_write(pidfile, (json.dumps(data) + "\n").encode())
            if interrupted is not None:
                raise SystemExit(128 + interrupted)
            try:
                process.wait(timeout=0.35)
            except subprocess.TimeoutExpired:
                pass
            if process.poll() is not None or not _recorder_running(data):
                detail = error_log.read_text(errors="replace").strip()[-2000:]
                raise RuntimeError(detail or "Screen recorder failed to start")
            return {"recording": True, "file": str(filename)}
        except BaseException:
            # Only this Popen child is signalled. Repeated termination signals
            # cannot interrupt cleanup; retain tracking unless exit is certain.
            cleaning = True
            exited = process is None or process.poll() is not None
            if process is not None and not exited:
                try:
                    process.send_signal(signal.SIGINT)
                    process.wait(timeout=5)
                    exited = True
                except ProcessLookupError:
                    exited = True
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                    exited = True
            if exited:
                pidfile.unlink(missing_ok=True)
            raise
        finally:
            for signum, previous in previous_handlers.items():
                signal.signal(signum, previous)


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv:
        raise ValueError("An action is required")
    command, *args = argv
    if command == "search-files":
        print(json.dumps(search_files(args[0] if args else "")))
    elif command == "clipboard":
        clipboard(args)
    elif command == "capture":
        result = capture(args)
        if result is not None:
            print(json.dumps(result))
    elif command == "annotation-session" and len(args) == 2:
        from .annotation import session
        session(args[0], args[1])
    elif command == "record":
        print(json.dumps(recording(args[0] if args else "start")))
    elif command == "open" and args:
        path = Path(args[0]).expanduser()
        if not path.exists():
            raise ValueError("The selected file no longer exists")
        spawn(["xdg-open", str(path.resolve())])
    elif command == "terminal":
        # Reuse Kitty's existing GPU process for near-instant new windows.
        terminal_args = [value.replace("--working-directory=", "--directory=", 1)
                         if value.startswith("--working-directory=") else value for value in args]
        spawn(["kitty", "--single-instance", *terminal_args])
    elif command == "files":
        spawn(["thunar", *(args or [str(Path.home())])])
    elif command == "browser":
        spawn(["brave"])
    elif command == "launch-desktop" and args:
        identifier = args[0]
        app_id = identifier.removesuffix(".desktop")
        if app_id == "com.mitchellh.ghostty":
            spawn(["ghostty", "--gtk-single-instance=false"])
            return 0
        if app_id.startswith("theme-switcher-"):
            from . import profiles
            profiles.apply_theme_live(app_id.removeprefix("theme-switcher-"))
            return 0
        if app_id == "thursday":
            from . import profiles
            run(["systemctl", "--user", "start", "thursday.service"])
            profiles.ipc("thursday", "focus")
            return 0
        from gi.repository import Gio, GLib
        try:
            entry = Gio.DesktopAppInfo.new(app_id + ".desktop")
        except (TypeError, GLib.Error) as error:
            raise ValueError("This application is no longer installed") from error
        if entry is None:
            raise ValueError("This application is no longer installed")
        entry.launch([], None)
    elif command == "wallpaper" and args:
        from . import themes, profiles
        home = profiles.home_path()
        theme = themes.import_wallpaper(Path(args[0]).expanduser(), home=home,
                                       state_dir=profiles.state_path(home), data_dir=profiles.data_path(home))
        print(json.dumps(profiles.apply_theme_live(theme["id"]), default=str))
    elif command == "project" and args:
        editor = next((candidate for candidate in ("antigravity", "code", "codium") if shutil.which(candidate)), None)
        if editor is None:
            raise RuntimeError("No supported project editor is installed")
        path = Path(args[0]).expanduser().resolve()
        if not path.exists():
            raise ValueError("Project does not exist")
        spawn([editor, str(path)])
    elif command == "audio-manager":
        spawn(["pwvucontrol"])
    elif command == "bluetooth-manager" or command == "bluetooth-pair":
        spawn(["blueman-manager"])
    elif command == "lock":
        run(["loginctl", "lock-session"])
    elif command == "brightness" and args:
        value = max(1, min(100, round(float(args[0]))))
        run(["brightnessctl", "set", f"{value}%"], stdout=subprocess.DEVNULL)
    elif command == "brightness-get":
        print(json.dumps({"percent": brightness_percent()}))
    elif command == "power-profile" and args and args[0] in {"power-saver", "balanced", "performance"}:
        run(["powerprofilesctl", "set", args[0]])
    elif command == "night-light-get":
        print(json.dumps(night_light_state()))
    elif command == "night-light":
        print(json.dumps(toggle_night_light()))
    elif command == "power" and args:
        choice = args[0]
        if choice in {"logout", "shutdown", "reboot"}:
            run([str(Path.home() / ".config" / "hypr" / "scripts" / f"safe-{choice}.sh")])
        elif choice == "suspend":
            run(["systemctl", "suspend"])
        else:
            raise ValueError("Unknown power action")
    elif command == "profile" and args:
        from .profiles import use_profile
        use_profile(args[0])
    else:
        raise ValueError(f"Unknown action: {command}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
