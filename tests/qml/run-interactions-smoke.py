#!/usr/bin/env python3
"""Exercise real Qt pointer/key events through shared controls and the launcher."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HARNESS = '''import QtQuick
import QtTest
import Quickshell
import QtQuick.Controls as Controls
import "config"
import "components" as C
ShellRoot {
    id: smoke
    QtObject { id: fakeApp; property var activeScreen: null; property int closed: 0; function open(name, screen) {} function close() { closed++; } }
    Window {
        id: hoverWin
        width: 680; height: 340
        visible: false
        color: Theme.desktopBackground
        Rectangle {
            id: hoverBoard
            anchors.fill: parent
            color: Theme.bgPanel
            C.Label { x: 24; y: 16; text: "Quiet controls"; color: Theme.textSoft }
            C.ActionButton { id: quietAction; x: 24; y: 48; width: 36; height: 28; quiet: true; iconName: "settings"; iconSize: 17; tooltip: "Control center" }
            C.QuickButton { id: quietQuick; x: 84; y: 45; quiet: true; compact: true; text: "Quiet action"; tooltip: "Action details" }
            C.WorkspaceButton { id: workspace; x: 225; y: 48; entry: ({id: 2, name: "2", windowCount: 2, active: false, urgent: false}) }
            C.Label { x: 24; y: 106; text: "Panel controls"; color: Theme.textSoft }
            C.ActionButton { id: panelAction; x: 24; y: 138; width: 150; text: "Panel action"; tooltip: "Panel action details" }
            C.QuickButton { id: panelQuick; x: 198; y: 136; width: 150; text: "Quick action"; tooltip: "Quick action details" }
            C.QuickTile { id: tile; x: 388; y: 136; text: "Wi-Fi"; subtitle: "Connected"; glyph: "⌁" }
            C.QuickDeviceRow { id: device; x: 24; y: 220; width: 324; text: "Headphones"; subtitle: "Connected"; glyph: "♪" }
        }
    }
    Window {
        id: win
        width: 900; height: 700; visible: true
        C.ActionButton { id: button; text: "Keyboard action"; tooltip: "Keyboard shortcut details"; property int presses: 0; onClicked: presses++ }
        C.ActionButton { id: dismiss; x: 200; text: "×"; font.pixelSize: 18; implicitHeight: 24 }
        C.QuickButton { id: compactButton; x: 300; compact: true; text: "Compact control"; glyph: "󰕾" }
        Launcher { id: launcher; y: 50; app: fakeApp }
        TestCase {
            name: "SumiKeyboard"
            when: win.visible
            function test_interactions() {
                wait(200);
                let failures = [];
                button.forceActiveFocus(Qt.OtherFocusReason);
                if (button.visualFocus || button.Controls.ToolTip.visible) failures.push("PROGRAMMATIC_FOCUS_PROMPT");
                dismiss.forceActiveFocus(Qt.OtherFocusReason);
                keyClick(Qt.Key_Tab, Qt.ShiftModifier);
                wait(650);
                if (!button.visualFocus || !button.Controls.ToolTip.visible) failures.push("KEYBOARD_FOCUS_CUE");
                for (const control of [button, dismiss, compactButton]) {
                    if (control.contentItem.height < control.contentItem.implicitHeight - 1) failures.push("BUTTON_CAPTION_CLIPPED " + control.text);
                }
                keyClick(Qt.Key_Return);
                keyClick(Qt.Key_Space);
                if (button.presses !== 2) failures.push("BUTTON_RETURN_SPACE " + button.presses);
                launcher.smokeSearchItem.forceActiveFocus();
                keyClick(Qt.Key_Tab, Qt.ControlModifier);
                if (launcher.tab !== "Files") failures.push("LAUNCHER_CTRL_TAB " + launcher.tab);
                keyClick(Qt.Key_Tab, Qt.ControlModifier | Qt.ShiftModifier);
                if (launcher.tab !== "Apps") failures.push("LAUNCHER_CTRL_SHIFT_TAB " + launcher.tab);
                launcher.smokeSearch = "";
                const before = launcher.smokeIndex;
                keyClick(Qt.Key_Down);
                if (launcher.entries.length > 1 && launcher.smokeIndex !== before + 1) failures.push("LAUNCHER_DOWN");
                if (!launcher.smokeSearchItem.activeFocus) failures.push("LAUNCHER_TYPING_FOCUS_LOST");
                keyClick(Qt.Key_F);
                if (launcher.smokeSearch !== "f") failures.push("LAUNCHER_TYPING");
                keyClick(Qt.Key_Escape);
                if (fakeApp.closed !== 1) failures.push("LAUNCHER_ESCAPE");

                hoverWin.visible = true;
                hoverWin.requestActivate();
                Settings.reducedMotion = true;
                wait(40);
                for (const control of [quietAction, quietQuick, workspace, panelAction, panelQuick, tile, device]) {
                    hoverBoard.forceActiveFocus(Qt.OtherFocusReason);
                    mouseMove(control, control.width / 2, control.height / 2);
                    wait(650);
                    if (!control.hovered) failures.push("POINTER_HOVER_NOT_DELIVERED " + control);
                    const background = control.background;
                    if (Math.abs(background.x) > 0.1 || Math.abs(background.y) > 0.1 || Math.abs(background.width - control.width) > 0.1 || Math.abs(background.height - control.height) > 0.1) failures.push("INSET_HOVER_BOX " + control + " " + [background.x, background.y, background.width, background.height]);
                    if (control.Controls.ToolTip.visible) failures.push("POINTER_TOOLTIP_BOX " + control);
                    if (!control.Accessible.name) failures.push("ACCESSIBLE_LABEL_MISSING " + control);
                    if ([quietAction, quietQuick, workspace].indexOf(control) >= 0) {
                        if (background.color.a !== 0) failures.push("QUIET_HOVER_FILL " + control);
                        const pixels = grabImage(hoverBoard);
                        const point = control.mapToItem(hoverBoard, 3, control.height / 2);
                        if (pixels.red(point.x, point.y) !== pixels.red(650, 300) || pixels.green(point.x, point.y) !== pixels.green(650, 300) || pixels.blue(point.x, point.y) !== pixels.blue(650, 300)) failures.push("QUIET_HOVER_VISIBLE_BOX " + control);
                        mousePress(control, control.width / 2, control.height / 2);
                        wait(16);
                        if (!control.down || background.color.a < 0.1) failures.push("PRESSED_CUE_MISSING " + control);
                        mouseRelease(control, control.width / 2, control.height / 2);
                    } else if (background.color.a < 0.06 || background.color.a > 0.11) failures.push("PANEL_HOVER_TOO_STRONG " + control);
                }
                mouseMove(quietAction, quietAction.width / 2, quietAction.height / 2);
                hoverBoard.forceActiveFocus(Qt.OtherFocusReason);
                wait(16);
                grabImage(hoverBoard).save("/tmp/sumi-controls-quiet-hover.png");
                for (const control of [quietAction, quietQuick, workspace]) {
                    control.forceActiveFocus(Qt.TabFocusReason);
                    wait(650);
                    if (!control.visualFocus || control.background.border.width < 2 || !control.Controls.ToolTip.visible) failures.push("QUIET_KEYBOARD_CUE_MISSING " + control);
                }
                hoverBoard.forceActiveFocus(Qt.OtherFocusReason);
                panelAction.selected = true; panelQuick.selected = true;
                workspace.entry = {id: 2, name: "2", windowCount: 2, active: true, urgent: false};
                mouseMove(tile, tile.width / 2, tile.height / 2);
                wait(16);
                if (panelAction.background.color !== Theme.accentBlue || panelQuick.background.color !== Theme.accentBlue || workspace.background.color.a < 0.17) failures.push("SELECTED_CUE_MISSING");
                grabImage(hoverBoard).save("/tmp/sumi-controls-panel-hover.png");
                if (failures.length) { console.error("SUMI_INTERACTIONS_FAILED", failures.join("; ")); Qt.exit(1); }
                else { console.info("SUMI_INTERACTIONS_OK"); Qt.quit(); }
            }
        }
    }
}
'''


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-interactions-") as temporary:
        work = Path(temporary)
        config = work / "shell"
        shutil.copytree(repo / "shell", config)
        launcher = config / "Launcher.qml"
        source = launcher.read_text().replace(
            "    property string initialTab:",
            "    property alias smokeSearch: search.text\n    readonly property var smokeSearchItem: search\n    property alias smokeIndex: results.currentIndex\n    property string initialTab:", 1)
        launcher.write_text(source)
        (config / "shell.qml").write_text(HARNESS)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, SUMI_PREVIEW="1", SUMI_STATE_DIR=str(work / "state"), QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(["qs", "-p", str(config)], env=environment, capture_output=True, text=True, timeout=15)
        output = result.stdout + result.stderr
        if result.returncode or "SUMI_INTERACTIONS_OK" not in output or any(message in output for message in ("TypeError:", "ReferenceError:", "Failed to load configuration", "Unable to assign [undefined]")):
            raise SystemExit(output)
        print("PASS: quiet controls have no pointer boxes/tooltips; panel hover fills complete targets gently; pressed/selected and keyboard focus cues remain; real Return/Space, Ctrl+Tab/reverse, arrows/search and Escape; captions fit normal/24px/compact controls")

if __name__ == "__main__":
    main()
