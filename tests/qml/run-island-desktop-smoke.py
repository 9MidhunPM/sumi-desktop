#!/usr/bin/env python3
"""Verify cached embedded tools and fresh/resumed launcher activation without desktop writes."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HARNESS = '''import QtQuick
import QtQuick.Controls
import QtTest
import Quickshell
import "components"
import "services" as S
ShellRoot {
    S.IslandSession { id: sharedSession }
    Component { id: anotherScreen; IslandDesktopPage { app: fakeApp; route: "widgets"; active: true; width: 640; height: 490 } }
    QtObject {
        id: fakeApp
        property var activeScreen: null
        property var codexStatus: null
        property var islandSession: sharedSession
        property bool nativeDialogOpen: false
        property bool focusRunning: false
        property double focusDeadline: 0
        property double focusRemaining: 1500000
        function close() {}
        function open(name, screen) { return true; }
        function focusReset(minutes) {}
        function focusStart() {}
        function focusPause() {}
    }
    FloatingWindow {
        visible: true; implicitWidth: 640; implicitHeight: 490
        IslandDesktopPage { id: page; anchors.fill: parent; app: fakeApp; active: true }
        TestCase {
            name: "IslandDesktop"
            when: true
            function check(value, message) { if (!value) { console.error("DESKTOP_FAILED", message); Qt.exit(1); throw new Error(message); } }
            function test_pages() {
                wait(300);
                check(page.ready, "Search is ready before first invocation");
                const launcher = findChild(page, "islandDesktopLauncherLoader").item;
                check(launcher.embedded, "Search uses embedded mode");
                page.route = "launcher"; page.prepare("launcher", true); wait(80);
                const search = findChild(launcher, "launcherSearch");
                search.text = "retained query";
                page.route = "desktop"; page.active = false; wait(40);
                page.active = true; page.route = "launcher"; page.prepare("launcher", false); wait(40);
                check(search.text === "retained query", "Resume retains query through close and navigation");
                page.prepare("launcher", true);
                check(search.text === "", "Explicit shortcut fresh-open clears query");
                page.route = "files"; wait(40);
                check(launcher.tab === "Files", "Route-only File deep link selects category");
                page.route = "clipboard"; wait(40);
                check(launcher.tab === "Clipboard", "Route-only Clipboard deep link selects category");
                page.route = "files"; wait(40);
                check(launcher.tab === "Files", "Back to Files restores correct category");
                page.route = "desktop"; wait(40);
                check(launcher.tab === "Apps" && launcher.visible, "Desktop alias opens Search without landing");
                page.route = "widgets"; wait(120);
                const widgets = findChild(page, "islandDesktopWidgetsLoader").item;
                check(widgets && widgets.embedded, "Widget editor embedded");
                widgets.priorityTexts = ["Keep this unfinished edit", "", ""]; widgets.dirty = true;
                check(sharedSession.savedPages.widgetsDraft.priorityTexts[0] === "Keep this unfinished edit", "Draft lives above monitor page lifetime");
                page.active = false;
                const other = anotherScreen.createObject(page.parent); wait(120);
                const otherWidgets = findChild(other, "islandDesktopWidgetsLoader").item;
                check(otherWidgets.priorityTexts[0] === "Keep this unfinished edit" && otherWidgets.dirty, "New monitor restores draft");
                otherWidgets.priorityTexts = ["Edited on the other monitor", "", ""];
                other.active = false; other.destroy();
                page.active = true; wait(60);
                check(widgets.priorityTexts[0] === "Edited on the other monitor", "Returning cached monitor restores latest draft");
                page.route = "appearance"; wait(120);
                const appearance = findChild(page, "islandDesktopAppearanceLoader").item;
                check(appearance && appearance.embedded && appearance.width <= page.width, "Appearance fits island viewport");
                page.route = "widgets"; wait(60); widgets.activatePanel();
                check(widgets.priorityTexts[0] === "Edited on the other monitor" && widgets.dirty, "Revisit keeps dirty widget draft");
                page.route = "codex"; wait(60);
                check(findChild(page, "islandDesktopCodexLoader").item === null, "Unconfigured Codex remains inert");
                console.info("ISLAND_DESKTOP_OK"); Qt.quit();
            }
        }
    }
}
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-island-desktop-") as directory:
        work = Path(directory)
        shell = work / "shell"
        shutil.copytree(repo / "shell", shell)
        (shell / "shell.qml").write_text(HARNESS)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, SUMI_PREVIEW="1", SUMI_DESKTOPCTL="/bin/false", SUMI_STATE_DIR=str(work / "state"), XDG_RUNTIME_DIR=str(runtime), QT_QPA_PLATFORM="offscreen")
        result = subprocess.run(["qs", "-p", str(shell)], env=environment, capture_output=True, text=True, timeout=20)
        output = result.stdout + result.stderr
        if result.returncode or "ISLAND_DESKTOP_OK" not in output or any(item in output for item in ["TypeError:", "ReferenceError:", "Failed to load configuration", "Unable to assign [undefined]", "Binding loop detected"]):
            raise SystemExit(output)
        print("PASS: warm search; fresh/resume queries; route-only Files/Clipboard/Back category sync; Desktop search alias; cached appearance/widgets; cross-monitor dirty draft migration; missing Codex")


if __name__ == "__main__":
    main()
