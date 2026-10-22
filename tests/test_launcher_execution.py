"""Real launcher events reach the real controller and a private desktop entry."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("qs"), "Quickshell is required")
class LauncherExecutionTests(unittest.TestCase):
    def test_return_launches_application_and_failed_click_stays_open_with_error(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="sumi-launch-exec-") as directory:
            work = Path(directory)
            config = work / "shell"
            shutil.copytree(repo / "shell", config)
            desktop = config / "services/Desktop.qml"
            desktop.write_text(desktop.read_text().replace('readonly property bool preview: Quickshell.env("SUMI_PREVIEW") === "1"', 'readonly property bool preview: false'))
            launcher = config / "Launcher.qml"
            launcher.write_text(launcher.read_text().replace("    property string initialTab:",
                "    property alias smokeSearch: search.text\n    readonly property var smokeSearchItem: search\n    readonly property var smokeResults: results\n    property string initialTab:", 1))
            applications = work / "data/applications"
            applications.mkdir(parents=True)
            marker = work / "launched"
            executable = work / "fixture-app"
            executable.write_text("#!/usr/bin/python3\nfrom pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('launched')\n")
            executable.chmod(0o755)
            for app_id, name, command in (("sumi-launch-fixture", "Launch Fixture", str(executable)),
                                          ("sumi-launch-broken", "Broken Fixture", "/nonexistent/sumi-fixture-executable")):
                (applications / (app_id + ".desktop")).write_text(f"[Desktop Entry]\nType=Application\nName={name}\nExec={command}\n")
            (config / "shell.qml").write_text('''
import QtQuick
import QtTest
import Quickshell
import "services" as S
ShellRoot {
    QtObject { id: fakeApp; property var activeScreen: null; property int closed: 0; function open(name, screen) { return true; } function close() { closed++; } }
    Window {
        id: win; width: 900; height: 700; visible: true
        Launcher { id: launcher; app: fakeApp }
        TestCase {
            when: win.visible
            name: "LauncherExecution"
            function check(value, message) {
                if (!value) { console.error("SUMI_LAUNCH_EXEC_FAILED", message, S.Desktop.lastError); Qt.exit(1); throw new Error(message); }
            }
            function test_application_activation() {
                wait(250);
                launcher.smokeSearch = "Launch Fixture";
                launcher.smokeSearchItem.forceActiveFocus();
                wait(50);
                check(launcher.entries.length === 1, "Fixture entry is searchable");
                check(launcher.height < 340 && launcher.smokeResults.height >= 66, "One result uses a compact, usable panel");
                keyClick(Qt.Key_Return);
                // The controller responds later: learning must use the query
                // which activated the app, even after the user edits it.
                launcher.smokeSearch = "Broken Fixture";
                tryCompare(S.Desktop, "pendingCount", 0, 4000);
                tryCompare(S.LauncherHistory, "busy", false, 4000);
                check(!S.Desktop.lastError && fakeApp.closed === 1, "Return launches and closes after success");
                wait(50);
                const row = launcher.smokeResults.itemAtIndex(0);
                check(!!row, "Broken entry is visible");
                mouseClick(row, row.width / 2, row.height / 2);
                tryCompare(S.Desktop, "pendingCount", 0, 4000);
                tryCompare(S.LauncherHistory, "busy", false, 4000);
                check(fakeApp.closed === 1, "Failed app stays in launcher");
                check(launcher.error.length > 0, "Failed app exposes actionable error in launcher");
                check(launcher.height <= 570 && launcher.smokeResults.height >= 66, "Failure leaves a usable result area");
                console.info("SUMI_LAUNCH_EXEC_OK");
                Qt.quit();
            }
        }
    }
}
''')
            runtime = work / "runtime"
            runtime.mkdir(mode=0o700)
            environment = dict(os.environ, SUMI_PREVIEW="1", SUMI_DESKTOPCTL=str(repo / "bin/desktopctl"),
                               SUMI_HOME=str(work), SUMI_STATE_DIR=str(work / "state"), HOME=str(work),
                               XDG_RUNTIME_DIR=str(runtime), QT_QPA_PLATFORM="offscreen",
                               XDG_DATA_HOME=str(work / "data"), XDG_DATA_DIRS=str(work / "empty-data"),
                               XDG_CONFIG_HOME=str(work / "xdg-config"), XDG_CACHE_HOME=str(work / "cache"),
                               DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(work / "absent-bus"))
            result = subprocess.run(["qs", "-p", str(config), "-n"], env=environment, text=True, capture_output=True, timeout=15)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("SUMI_LAUNCH_EXEC_OK", output)
            self.assertTrue(marker.exists(), "Actual .desktop Exec command did not run: " + output)
            history_path = work / "state/launcher-history.json"
            history = json.loads(history_path.read_text())
            self.assertEqual(set(history["entries"]), {"app:sumi-launch-fixture"})
            learned = history["entries"]["app:sumi-launch-fixture"]
            self.assertEqual(learned["count"], 1, "One activation must create one history event")
            self.assertEqual(set(learned["queries"]), {"launch fixture"})
            self.assertEqual(learned["queries"]["launch fixture"]["count"], 1)
            # A fresh process proves the singleton loads durable state and the
            # launcher's empty-search ordering uses it after a restart.
            (config / "shell.qml").write_text('''
import QtQuick
import QtTest
import Quickshell
import "services" as S
ShellRoot {
    QtObject { id: fakeApp; property var activeScreen: null; function open(name, screen) { return true; } function close() {} }
    Window {
        id: win; width: 900; height: 700; visible: true
        Launcher { id: launcher; app: fakeApp }
        TestCase {
            when: win.visible
            name: "LauncherRestart"
            function test_persistent_ranking() {
                tryCompare(S.LauncherHistory, "loaded", true, 4000);
                compare(S.LauncherHistory.document.entries["app:sumi-launch-fixture"].count, 1);
                compare(launcher.entries[0].historyId, "app:sumi-launch-fixture");
                console.info("SUMI_LAUNCH_RESTART_OK");
                Qt.quit();
            }
        }
    }
}
''')
            restarted = subprocess.run(["qs", "-p", str(config), "-n"], env=environment, text=True, capture_output=True, timeout=15)
            restart_output = restarted.stdout + restarted.stderr
            self.assertEqual(restarted.returncode, 0, restart_output)
            self.assertIn("SUMI_LAUNCH_RESTART_OK", restart_output)
            self.assertEqual(json.loads(history_path.read_text()), history, "Reading history must not record usage")


if __name__ == "__main__":
    unittest.main()
