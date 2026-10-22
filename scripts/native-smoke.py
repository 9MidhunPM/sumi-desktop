#!/usr/bin/env python3
"""Exercise Sumi on an isolated nested compositor with synthetic user content.

Requires an explicitly selected parent Wayland socket with linux-dmabuf support.
The parent receives one nested window; input and screenshots target only its
child compositor. No host configuration, services, clipboard, or bus are used.
Example: python scripts/native-smoke.py --parent-wayland /run/user/1000/wayland-1
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import select
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))


def wait_for(check, *, timeout=10, label="condition"):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except (OSError, ValueError, subprocess.SubprocessError, AssertionError) as error:
            last = error
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for {label}: {last or 'not ready'}")


def worker(work: Path, output: Path, parent: Path) -> dict:
    from sumi import session, themes, widgets
    from sumi.scenes import scene_for_theme
    config, data, state, runtime = (work / name for name in ("config", "data", "state", "r"))
    for path in (config, data, state, runtime, work / "empty-data"):
        path.mkdir(parents=True, mode=0o700, exist_ok=True)
    environment = dict(os.environ)
    environment.update(
        HOME=str(work), XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(data),
        XDG_STATE_HOME=str(work / "xdg-state"), XDG_CACHE_HOME=str(work / "cache"),
        XDG_RUNTIME_DIR=str(runtime), XDG_DATA_DIRS=str(work / "empty-data"),
        DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(work / "no-system-bus"),
        SUMI_HOME=str(work), SUMI_STATE_DIR=str(state), SUMI_DATA_DIR=str(data / "sumi"),
        SUMI_DESKTOPCTL=str(ROOT / "bin/desktopctl"), SUMI_PREVIEW="0",
        QT_QPA_PLATFORM="wayland", QS_NO_RELOAD_POPUP="1", PYTHONDONTWRITEBYTECODE="1",
        LIBSEAT_BACKEND="sumi-test-disabled", HYPRLAND_NO_SD_VARS="1",
        HYPRLAND_NO_SD_NOTIFY="1", HYPRLAND_NO_CRASHREPORTER="1",
        WAYLAND_DISPLAY=str(parent), XDG_CURRENT_DESKTOP="Hyprland",
    )
    # Hardware values are synthetic screenshot fixtures. All other controller
    # calls, including real launch history and notifications, use production code.
    controller = work / "fixture-controller"
    controller.write_text("#!/usr/bin/python3\nimport json, os, sys\n"
                          "if sys.argv[1:] == ['action', 'brightness-get']:\n print(json.dumps({'percent': 62})); raise SystemExit(0)\n"
                          "if sys.argv[1:] == ['action', 'night-light-get']:\n print(json.dumps({'available': False, 'active': False, 'temperature': None})); raise SystemExit(0)\n"
                          "os.execv(" + repr(str(ROOT / "bin/desktopctl")) + ", [" + repr(str(ROOT / "bin/desktopctl")) + ", *sys.argv[1:]])\n")
    controller.chmod(0o755)
    environment["SUMI_DESKTOPCTL"] = str(controller)
    # Explicit nonexistent libseat backend fails before touching physical seats.
    # HYPRLAND_NO_SD_VARS also disables compositor-owned manager env changes.
    for key in ("DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE", "NOTIFY_SOCKET", "XDG_SESSION_ID"):
        environment.pop(key, None)
    # This process already runs on the newly created private bus. Keep Python
    # renderers and subprocesses on the same explicit XDG roots.
    os.environ.clear()
    os.environ.update(environment)
    for path, (content, mode) in session.build_artifacts(ROOT, config, data / "sumi", state, work / "bin", home=work).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(mode)
    compositor_config = config / "hypr/hyprland.lua"
    lines = compositor_config.read_text().splitlines()
    # Session units are covered separately. A nested test must never start the
    # real user's systemd units or import a second compositor environment.
    lines = [line for line in lines if not line.startswith('hl.on("hyprland.')]
    lines += [
        'hl.monitor({ output = "SUMI-QA", mode = "1600x1000@60", position = "0x0", scale = 1 })',
        'hl.config({ misc = { disable_watchdog_warning = true, disable_hyprland_guiutils_check = true }, ecosystem = { no_update_news = true, no_donation_nag = true } })',
    ]
    compositor_config.write_text("\n".join(lines) + "\n")
    theme = themes.get_theme("sumi-ember", state_dir=state, data_dir=data / "sumi", home=work)
    for path, content in themes.render_theme(theme, home=work, state_dir=state)[0].items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (state / "scene.json").write_text(json.dumps(scene_for_theme(theme)))
    document = widgets.defaults()
    document["priorities"] = [{"text": "Read a chapter", "done": False}, {"text": "Make something useful", "done": True}, {"text": "Take a quiet break", "done": False}]
    (state / "widgets.json").write_text(json.dumps(document))
    marker = work / "fixture-launched"
    application = work / "fixture-app"
    application.write_text("#!/usr/bin/python3\nfrom pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('launched')\n")
    application.chmod(0o755)
    entries = data / "applications"
    entries.mkdir(parents=True)
    (entries / "sumi-notes.desktop").write_text('[Desktop Entry]\nType=Application\nName=Sumi Notes\nComment=Synthetic application for release verification\nIcon=accessories-text-editor\nExec="' + str(application) + '"\n')
    processes = []
    logs = []
    report = {"mode": "nested-native", "synthetic_content": True,
              "hardware_fixtures": ["brightness", "night-light"], "host_services_started": False, "checks": {}}

    def launch(argv, name):
        log = (output / name).open("w")
        logs.append(log)
        process = subprocess.Popen(argv, env=environment, stdout=log, stderr=subprocess.STDOUT)
        processes.append(process)
        return process

    def call(*argv):
        result = subprocess.run(list(argv), env=environment, capture_output=True, text=True, timeout=8)
        if result.returncode:
            raise AssertionError(result.stderr.strip() or result.stdout.strip() or repr(argv))
        return result.stdout.strip()

    def ipc(target, method, *arguments):
        return call("qs", "ipc", "-p", str(ROOT / "shell"), "call", target, method, *arguments)

    def status():
        return json.loads(ipc("sumi", "status"))

    def capture(name):
        time.sleep(0.4)
        call("grim", str(output / name))

    try:
        compositor = launch(["Hyprland", "-c", str(compositor_config)], "hyprland.log")

        def instance_ready():
            if compositor.poll() is not None:
                raise RuntimeError("Nested Hyprland failed; inspect hyprland.log (parent requires linux-dmabuf and a render node)")
            return next((path for path in (runtime / "hypr").glob("*/.socket.sock")), None)

        endpoint = wait_for(instance_ready, label="nested Hyprland IPC")
        environment["HYPRLAND_INSTANCE_SIGNATURE"] = endpoint.parent.name
        environment["WAYLAND_DISPLAY"] = str(runtime / "wayland-1")
        os.environ.update(environment)
        wait_for(lambda: call("hyprctl", "-j", "monitors") != "[]", label="nested monitor")
        # A headless output retains the nested GPU allocator without inheriting
        # the parent's tiling geometry. Only the private compositor is addressed.
        call("hyprctl", "output", "create", "headless", "SUMI-QA")
        wait_for(lambda: any(item["name"] == "SUMI-QA" for item in json.loads(call("hyprctl", "-j", "monitors"))), label="isolated capture output")
        call("hyprctl", "output", "remove", "WAYLAND-1")
        wait_for(lambda: [item["name"] for item in json.loads(call("hyprctl", "-j", "monitors"))] == ["SUMI-QA"], label="isolated output geometry")
        errors = call("hyprctl", "configerrors")
        if errors.strip():
            raise AssertionError("Compositor configuration errors: " + errors)
        report["checks"]["hyprland_config"] = True
        launch(["awww-daemon"], "wallpaper.log")
        wait_for(lambda: call("awww", "query"), label="wallpaper daemon")
        session.restore_wallpaper(state_dir=state, home=work)
        launch(["qs", "-p", str(ROOT / "shell"), "-n"], "quickshell.log")
        wait_for(lambda: ipc("sumi", "ping") == "pong", label="Sumi shell")
        report["checks"]["shell_startup"] = True
        capture("desktop.png")
        ipc("sumi", "open", "launcher")
        wait_for(lambda: status()["panel"] == "launcher", label="launcher open")
        time.sleep(0.4)
        call("wtype", "Sumi Notes")
        time.sleep(0.3)
        capture("launcher.png")
        call("wtype", "-k", "Return")
        wait_for(marker.exists, label="synthetic application launch from keyboard")
        history = state / "launcher-history.json"
        wait_for(lambda: history.exists() and "app:sumi-notes" in json.loads(history.read_text()).get("entries", {}), label="launcher learning")
        report["checks"]["launcher_keyboard_and_learning"] = True
        ipc("sumi", "open", "settings")
        wait_for(lambda: status()["panel"] == "settings", label="quick settings open")
        capture("quick-settings.png")
        call("wtype", "-k", "Escape")
        wait_for(lambda: status()["panel"] == "", label="keyboard Escape")
        report["checks"]["quick_settings_and_keyboard_close"] = True
        call("gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications", "--object-path", "/org/freedesktop/Notifications", "--method", "org.freedesktop.Notifications.Notify", "Sumi", "0", "", "A quiet moment", "Your desktop is ready. This is synthetic release content.", "[]", "{}", "0")
        wait_for(lambda: status()["notifications"] >= 1, label="notification delivery")
        capture("notification.png")
        ipc("sumi", "open", "notifications")
        capture("notifications.png")
        report["checks"]["notifications_private_dbus"] = True
        ipc("sumi", "close")
        cool = themes.get_theme("sumi-tide", state_dir=state, data_dir=data / "sumi", home=work)
        for path, content in themes.render_theme(cool, home=work, state_dir=state)[0].items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        session.restore_wallpaper(state_dir=state, home=work)
        call("hyprctl", "reload")
        if call("hyprctl", "configerrors").strip():
            raise AssertionError("Theme reload introduced compositor configuration errors")
        wait_for(lambda: status()["theme"] == "sumi-tide", label="theme refresh")
        if cool["wallpaper"] not in call("awww", "query"):
            raise AssertionError("Wallpaper daemon did not report the selected image")
        capture("cool-desktop.png")
        report["checks"]["wallpaper_theme_refresh"] = True
        layers = json.loads(call("hyprctl", "-j", "layers"))
        report["checks"]["native_layers"] = "sumi-bar" in json.dumps(layers)
        report["passed"] = all(report["checks"].values())
        return report
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
        for log in logs:
            log.close()
        for index, internal_log in enumerate((runtime / "hypr").glob("*/hyprland.log")):
            shutil.copyfile(internal_log, output / f"hyprland-internal-{index}.log")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-wayland", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    parent = args.parent_wayland
    if not parent.is_absolute() or not stat.S_ISSOCK(parent.stat().st_mode):
        parser.error("--parent-wayland must name an absolute, existing Wayland socket")
    if args.worker:
        try:
            result = worker(args.worker, args.output, parent)
        except Exception as error:
            result = {"passed": False, "error": str(error), "mode": "nested-native"}
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return 0 if result.get("passed") else 1
    missing = [name for name in ("Hyprland", "hyprctl", "qs", "awww", "awww-daemon", "grim", "wtype", "gdbus", "dbus-daemon") if not shutil.which(name)]
    if missing:
        parser.error("Missing native QA dependencies: " + ", ".join(missing))
    output = args.output or Path(tempfile.mkdtemp(prefix="sumi-native-artifacts-"))
    output = output.absolute()
    output.mkdir(parents=True, exist_ok=True)
    # Linux AF_UNIX socket paths have a 108-byte ceiling; Hyprland appends its
    # long instance signature and .socket2.sock below XDG_RUNTIME_DIR.
    with tempfile.TemporaryDirectory(prefix="sn-") as temporary:
        work = Path(temporary)
        runtime = work / "r"
        runtime.mkdir(mode=0o700)
        environment = {"PATH": os.environ.get("PATH", "/usr/bin"), "LANG": "C.UTF-8", "HOME": str(work), "XDG_RUNTIME_DIR": str(runtime), "PYTHONDONTWRITEBYTECODE": "1"}
        # No standard_session_servicedirs: neither host portals nor their FUSE
        # document mounts can activate on this bus. Tests own their names directly.
        bus_config = work / "bus.conf"
        bus_config.write_text('<busconfig><type>session</type><listen>unix:tmpdir=' + escape(str(runtime)) + '</listen>'
                              '<auth>EXTERNAL</auth><policy context="default"><allow send_destination="*"/>'
                              '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        with (output / "dbus.log").open("w") as log:
            bus = subprocess.Popen(["dbus-daemon", "--nofork", "--print-address=1", "--config-file=" + str(bus_config)], env=environment, stdout=subprocess.PIPE, stderr=log, text=True)
            try:
                if not select.select([bus.stdout], [], [], 5)[0]:
                    raise RuntimeError("Private D-Bus did not become ready")
                address = bus.stdout.readline().strip()
                if not address.startswith("unix:"):
                    raise RuntimeError("Private D-Bus returned an invalid address")
                environment["DBUS_SESSION_BUS_ADDRESS"] = address
                result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--parent-wayland", str(parent), "--output", str(output), "--worker", str(work)], env=environment)
            finally:
                bus.terminate()
                bus.wait(timeout=5)
        print("Native QA artifacts:", output)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
