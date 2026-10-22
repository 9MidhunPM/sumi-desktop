#!/usr/bin/env python3
"""Exercise the real editor, including local dates, focus scrolling and preview isolation."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "config"
import "services" as S
ShellRoot {
    QtObject { id: screenInfo; property int width: 1280; property int height: 900 }
    QtObject { id: fakeApp; property var activeScreen: screenInfo; function close() {} }
    Window {
        id: win; width: screenInfo.width; height: screenInfo.height; visible: true; color: Theme.desktopBackground
        WidgetsEditor { id: editor; app: fakeApp; anchors.centerIn: parent }
        TestCase {
            name: "WidgetEditor"; when: win.visible
            function verify(value, message) { if (!value) { console.error("WIDGET_EDITOR_FAILED", message || "Assertion failed"); Qt.exit(1); throw new Error(message || "Assertion failed"); } }
            function compare(actual, expected, message) { verify(actual === expected, (message || "Mismatch") + ": " + actual + " != " + expected); }
            function test_editor() {
                try {
                tryVerify(() => S.Widgets.loaded);
                const first = findChild(editor, "widgetsPriority0");
                editor.focusDefault();
                for (const character of "Finish the next chapter") keyClick(character);
                compare(editor.priorityTexts[0], "Finish the next chapter");
                verify(editor.dirty);
                const done = findChild(editor, "widgetsDone0");
                mouseClick(done);
                verify(editor.priorityDone[0]);
                for (const key of ["clock", "spotify", "priorities", "deadline"]) {
                    const toggle = findChild(editor, "widgetsEnabled" + key);
                    toggle.clicked();
                    compare(editor.enabledDraft[key], false);
                    toggle.clicked();
                    compare(editor.enabledDraft[key], true);
                }
                verify(editor.parseDeadline("2028-02-29", "17:30").ok);
                verify(!editor.parseDeadline("2027-02-29", "17:30").ok);
                verify(!editor.parseDeadline("2026-04-31", "17:30").ok);
                verify(!editor.parseDeadline("2026-10-22", "24:00").ok);
                verify(!editor.parseDeadline("22/10/2026", "17:30").ok);
                compare(editor.parseDeadline("", "17:00").at, null);
                const date = findChild(editor, "widgetsDeadlineDate");
                const time = findChild(editor, "widgetsDeadlineTime");
                const title = findChild(editor, "widgetsDeadlineTitle");
                date.text = "2026-02-30"; time.text = "17:00"; editor.save();
                verify(editor.message.indexOf("valid") >= 0);
                date.text = "2026-10-22"; title.text = "Project review"; editor.save();
                verify(editor.message.indexOf("Preview") >= 0);
                verify(S.Widgets.document.priorities[0].text === "");
                for (const size of [[480,360], [600,440], [960,540], [1280,900]]) {
                    screenInfo.width = size[0]; screenInfo.height = size[1]; wait(100);
                    verify(editor.width <= size[0] - 48 && editor.height <= size[1] - 48);
                    editor.focusDefault(); wait(20);
                    const seen = {};
                    for (let i = 0; i < 22; i++) {
                        let focused = win.activeFocusItem;
                        while (focused && !focused.objectName && focused !== editor) focused = focused.parent;
                        if (focused && focused.objectName.startsWith("widgets")) {
                            seen[focused.objectName] = true;
                            const p = focused.mapToItem(editor, 0, 0);
                            verify(p.x >= -1 && p.y >= -1 && p.x + focused.width <= editor.width + 1 && p.y + focused.height <= editor.height + 1, focused.objectName + " fits " + size);
                        }
                        keyClick(Qt.Key_Tab); wait(20);
                    }
                    verify(seen.widgetsPriority0 && seen.widgetsDeadlineDate && seen.widgetsSave, "Core controls reachable at " + size);
                }
                editor.grabToImage(result => result.saveToFile("/tmp/sumi-widgets-editor.png"));
                wait(200);
                console.info("SUMI_WIDGET_EDITOR_OK"); Qt.quit();
                } catch (error) { console.error("WIDGET_EDITOR_FAILED", String(error), error.stack); Qt.exit(1); }
            }
        }
    }
}
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-widget-editor-") as temporary:
        work = Path(temporary)
        config = work / "shell"
        shutil.copytree(repo / "shell", config)
        (config / "shell.qml").write_text(HARNESS)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        state = work / "state"
        environment = dict(os.environ, SUMI_PREVIEW="1", SUMI_STATE_DIR=str(state), SUMI_DESKTOPCTL=str(repo / "bin/desktopctl"), QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(["qs", "-p", str(config)], env=environment, capture_output=True, text=True, timeout=20)
        output = result.stdout + result.stderr
        if result.returncode or "SUMI_WIDGET_EDITOR_OK" not in output or any(value in output for value in ("TypeError:", "ReferenceError:", "Failed to load configuration", "Unable to assign [undefined]", "FAIL!", "Binding loop")):
            raise SystemExit(output)
        if (state / "widgets.json").exists():
            raise SystemExit("Preview modified personal widget state")
        print("PASS: priorities/visibility edits; strict local dates; invalid and preview saves; focus scrolling at four sizes; no preview writes")


if __name__ == "__main__":
    main()
