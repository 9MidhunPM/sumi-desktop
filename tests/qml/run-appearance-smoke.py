#!/usr/bin/env python3
"""Exercise Appearance's real scroll/focus layout at short logical screen sizes."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "config"
ShellRoot {
    QtObject { id: screenInfo; property int width: 1280; property int height: 900 }
    QtObject { id: fakeApp; property var activeScreen: screenInfo; property bool nativeDialogOpen: false; property int openings: 0; function close() {} function open(name, screen) { openings++; } }
    Window {
        id: win
        width: screenInfo.width; height: screenInfo.height; visible: true
        Appearance { id: appearance; app: fakeApp; anchors.centerIn: parent }
        TestCase {
            name: "SumiAppearance"
            when: win.visible
            function assertTrue(condition, message) {
                if (!condition) { console.error("SUMI_APPEARANCE_FAILED", message); Qt.exit(1); throw new Error(message); }
            }
            function waitFor(condition, label) {
                let elapsed = 0;
                while (!condition() && elapsed < 4000) { wait(20); elapsed += 20; }
                assertTrue(condition(), label);
            }
            function fits(item, container) {
                const position = item.mapToItem(container, 0, 0);
                return position.x >= -1 && position.y >= -1 && position.x + item.width <= container.width + 1 && position.y + item.height <= container.height + 1;
            }
            function fullyVisible(item) {
                if (!fits(item, appearance)) return false;
                let ancestor = item.parent;
                while (ancestor && ancestor !== appearance) {
                    if (ancestor.clip && !fits(item, ancestor)) return false;
                    ancestor = ancestor.parent;
                }
                return true;
            }
            function test_layoutAndKeyboard() {
                Settings.reducedMotion = true;
                waitFor(() => appearance.themeCount >= 22, "Theme catalog loads");
                const gallery = findChild(appearance, "appearanceGallery");
                const accent = findChild(appearance, "appearanceAccent");
                const applyAccent = findChild(appearance, "appearanceApplyAccent");
                const recovery = findChild(appearance, "appearanceClassic");
                assertTrue(!recovery.visible, "Recovery is hidden without a usable previous-desktop backup");
                const names = ["appearanceGallery", "appearanceAddWallpaper", "appearanceClose", "appearanceAccent", "appearanceApplyAccent", "appearanceApplyTheme", "appearanceBarMode", "appearanceMotion"];
                assertTrue(appearance.galleryWidth > 200 && appearance.previewWidth > 0 && appearance.previewWidth <= 260, "Default gallery and preview metrics remain valid");
                for (const size of [[480, 360], [600, 440], [960, 540], [1280, 720]]) {
                    screenInfo.width = size[0]; screenInfo.height = size[1]; wait(100);
                    assertTrue(appearance.width <= size[0] - 48 && appearance.height <= size[1] - 48, "Panel fits " + size);
                    assertTrue(gallery.height >= 134 && gallery.width >= 160, "Gallery remains usable at " + size);
                    appearance.focusDefault(); wait(60);
                    assertTrue(fullyVisible(gallery), "Focused gallery visible at " + size);
                    const initial = gallery.currentIndex;
                    keyClick(Qt.Key_Down); wait(30);
                    assertTrue(gallery.currentIndex !== initial && appearance.selected.id === appearance.themes[gallery.currentIndex].id, "Arrow selection works at " + size);
                    keyClick(Qt.Key_Return); wait(30);
                    assertTrue(appearance.message.indexOf("Preview") === 0, "Enter applies selected theme through preview guard");
                    const visited = {};
                    for (let index = 0; index < 35; index++) {
                        let focused = win.activeFocusItem;
                        while (focused && focused !== appearance && names.indexOf(focused.objectName) < 0) focused = focused.parent;
                        if (focused && names.indexOf(focused.objectName) >= 0) {
                            visited[focused.objectName] = true;
                            assertTrue(fullyVisible(focused), focused.objectName + " is scrolled into view at " + size);
                        }
                        keyClick(Qt.Key_Tab); wait(35);
                    }
                    for (const name of names) assertTrue(visited[name], name + " is reachable by Tab at " + size + " visited=" + Object.keys(visited).join(","));
                    for (let index = 0; index < 15; index++) { keyClick(Qt.Key_Tab, Qt.ShiftModifier); wait(35); }
                    assertTrue(win.activeFocusItem !== null, "Reverse navigation retains focus");
                }
                appearance.recoveryAvailable = true; wait(30);
                assertTrue(recovery.visible && recovery.enabled, "Recovery is exposed only after a usable backup is reported");
                appearance.recoveryAvailable = false;
                appearance.selected = null;
                accent.text = "#aabbcc";
                wait(30);
                assertTrue(!applyAccent.enabled, "Accent application needs a selected theme");
                keyClick(Qt.Key_O, Qt.ControlModifier);
                waitFor(() => appearance.smokePicker.visible, "Wallpaper picker opens with its mapped parent");
                assertTrue(fakeApp.nativeDialogOpen, "Picker requests exclusive-layer input handoff");
                appearance.smokePicker.reject();
                waitFor(() => !fakeApp.nativeDialogOpen && fakeApp.openings === 1, "Cancel restores Appearance and keyboard ownership");
                console.info("SUMI_APPEARANCE_OK"); Qt.quit();
            }
        }
    }
}
'''


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-appearance-") as temporary:
        work = Path(temporary)
        config = work / "shell"
        shutil.copytree(repo / "shell", config)
        appearance = config / "Appearance.qml"
        appearance.write_text(appearance.read_text().replace("    required property var app", "    readonly property var smokePicker: importer\n    required property var app", 1))
        (config / "shell.qml").write_text(HARNESS)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, SUMI_PREVIEW="1", SUMI_STATE_DIR=str(work / "state"), SUMI_DESKTOPCTL=str(repo / "bin/desktopctl"), QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(["qs", "-p", str(config)], env=environment, capture_output=True, text=True, timeout=25)
        output = result.stdout + result.stderr
        if result.returncode or "SUMI_APPEARANCE_OK" not in output or any(message in output for message in ("TypeError:", "ReferenceError:", "Failed to load configuration", "Unable to assign [undefined]", "FAIL!", "Binding loop")):
            raise SystemExit(output)
        print("PASS: Appearance controls fit their scroll viewports and are Tab-reachable at 480x360, 600x440, 960x540, 1280x720; gallery arrows/Enter; default metrics; null-selection guard")


if __name__ == "__main__":
    main()
