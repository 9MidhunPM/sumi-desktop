"""Real Notify delivery on an isolated bus; never claims the user's service."""
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest


def worker(work: Path) -> None:
    config = work / "shell"
    environment = dict(os.environ, HOME=str(work), XDG_CONFIG_HOME=str(work / "config"),
                       XDG_DATA_HOME=str(work / "data"), XDG_CACHE_HOME=str(work / "cache"),
                       SUMI_STATE_DIR=str(work / "state"), SUMI_PREVIEW="0", SUMI_DRY_RUN="1",
                       SUMI_DESKTOPCTL=str(Path(__file__).resolve().parents[1] / "bin/desktopctl"),
                       SUMI_HOME=str(work), QT_QPA_PLATFORM="offscreen", QS_NO_RELOAD_POPUP="1",
                       XDG_RUNTIME_DIR=str(work / "runtime"))
    log_path = work / "quickshell.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(["qs", "-p", str(config), "-n"], env=environment, stdout=log, stderr=subprocess.STDOUT)
        def call(*arguments):
            result = subprocess.run(list(arguments), env=environment, text=True, capture_output=True, timeout=4)
            if result.returncode:
                raise AssertionError(result.stderr or result.stdout)
            return result.stdout.strip()
        def status():
            return json.loads(call("qs", "ipc", "-p", str(config), "call", "notificationTest", "status"))
        def wait_for(check):
            deadline = time.monotonic() + 4
            value = None
            while time.monotonic() < deadline:
                try:
                    value = check()
                except (json.JSONDecodeError, AssertionError):
                    # IPC can briefly close or return no body while Quickshell
                    # hands its endpoint to the replacement QML generation.
                    value = None
                if value:
                    return value
                time.sleep(.05)
            raise AssertionError("Notification state did not update")
        def notify(summary, *, replace=0, actions="['default', 'Open']", timeout=0):
            output = call("gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
                          "--object-path", "/org/freedesktop/Notifications", "--method", "org.freedesktop.Notifications.Notify",
                          "Sumi native fixture", str(replace), "", summary, "Body <b>without markup</b>", actions, "{}", str(timeout))
            return int(re.search(r"uint32 (\d+)", output)[1])
        def restart():
            nonlocal process
            process.terminate()
            process.wait(timeout=3)
            process = subprocess.Popen(["qs", "-p", str(config), "-n"], env=environment, stdout=log, stderr=subprocess.STDOUT)
            wait_for(lambda: "true" in call("gdbus", "call", "--session", "--dest", "org.freedesktop.DBus", "--object-path", "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.NameHasOwner", "org.freedesktop.Notifications"))
            wait_for(lambda: status()["loaded"] and not status()["busy"])
        try:
            wait_for(lambda: "true" in call("gdbus", "call", "--session", "--dest", "org.freedesktop.DBus", "--object-path", "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.NameHasOwner", "org.freedesktop.Notifications"))
            first_id = notify("Original summary")
            wait_for(lambda: status()["count"] == 1)
            first = status()["history"][0]
            assert first["summary"] == "Original summary" and first["body"] == "Body without markup", first
            assert first["actions"] == ["Open"] and first["popup"], first
            assert notify("Replacement summary", replace=first_id, actions="['default', 'Updated action']") == first_id
            wait_for(lambda: status()["history"][0]["summary"] == "Replacement summary")
            updated = status()
            assert updated["count"] == 1 and updated["history"][0]["actions"] == ["Updated action"], updated
            call("qs", "ipc", "-p", str(config), "call", "notificationTest", "dnd", "true")
            notify("Silent history", actions="[]", timeout=200)
            wait_for(lambda: status()["count"] == 2)
            time.sleep(.3)
            silent = status()
            assert silent["active"] == 0 and silent["history"][0]["summary"] == "Silent history", silent
            wait_for(lambda: not status()["busy"])
            assert not status()["storageError"], status()
            assert stat.S_IMODE((work / "state").stat().st_mode) == 0o700
            assert stat.S_IMODE((work / "state/notifications.json").stat().st_mode) == 0o600
            harness = config / "shell.qml"
            harness.write_text(harness.read_text().replace("generation: 1", "generation: 2"))
            wait_for(lambda: status()["generation"] == 2 and status()["loaded"] and not status()["busy"])
            reloaded = status()
            assert reloaded["count"] == 2 and reloaded["active"] == 0, reloaded
            assert any(item["summary"] == "Silent history" for item in reloaded["history"]), reloaded
            restart()
            restored = status()
            assert restored["count"] == 2 and restored["active"] == 0, restored
            assert all(not item["actions"] for item in restored["history"]), restored
            notify("New session entry", actions="[]", timeout=200)
            wait_for(lambda: status()["count"] == 3)
            call("qs", "ipc", "-p", str(config), "call", "notificationTest", "clear")
            assert status()["count"] == 0
            wait_for(lambda: not status()["busy"])
            restart()
            assert status()["count"] == 0, status()
            print("SUMI_NATIVE_NOTIFICATIONS_OK")
        except BaseException:
            print("QS_PROCESS_RETURN", process.poll(), file=sys.stderr)
            try:
                print("LAST_NOTIFICATION_STATE", call("qs", "ipc", "-p", str(config), "call", "notificationTest", "status"), file=sys.stderr)
            except Exception as error:
                print("LAST_NOTIFICATION_STATE_ERROR", error, file=sys.stderr)
            if (work / "state/notifications.json").exists():
                print("SAVED_NOTIFICATION_STATE", (work / "state/notifications.json").read_text(), file=sys.stderr)
            print(log_path.read_text(), file=sys.stderr)
            raise
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


@unittest.skipUnless(all(shutil.which(command) for command in ("qs", "gdbus", "dbus-run-session")), "Native QML/DBus programs required")
class NotificationDbusTests(unittest.TestCase):
    def test_real_notify_replace_expiry_and_dnd_on_private_bus(self):
        probe = subprocess.run(["dbus-run-session", "--", "/usr/bin/true"], capture_output=True, text=True, timeout=5)
        if "Operation not permitted" in probe.stderr:
            self.skipTest("Sandbox forbids private D-Bus socket; run this test in the native host lane")
        self.assertEqual(probe.returncode, 0, probe.stderr)
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="sumi-notification-bus-") as directory:
            work = Path(directory)
            shutil.copytree(repo / "shell", work / "shell")
            (work / "runtime").mkdir(mode=0o700)
            (work / "shell/shell.qml").write_text('''
import QtQuick
import Quickshell
import Quickshell.Io
import "config" as C
import "services" as S
ShellRoot {
    id: root
    readonly property int generation: 1
    readonly property int count: S.Notifications.count
    IpcHandler {
        target: "notificationTest"
        function status(): string { return JSON.stringify({generation: root.generation, count: S.Notifications.count, active: S.Notifications.active.length, history: S.Notifications.history, loaded: S.Notifications.historyLoaded, busy: S.Notifications.persistenceBusy, storageError: S.Notifications.storageError}); }
        function dnd(value: bool): void { C.Settings.setValue("dnd", value); }
        function clear(): void { S.Notifications.clear(); }
    }
}
''')
            result = subprocess.run(["dbus-run-session", "--", sys.executable, str(Path(__file__).resolve()), "--worker", str(work)],
                                    capture_output=True, text=True, timeout=25)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("SUMI_NATIVE_NOTIFICATIONS_OK", result.stdout)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        worker(Path(sys.argv[2]))
    else:
        unittest.main()
