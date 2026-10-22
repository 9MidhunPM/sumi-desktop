#!/usr/bin/env python3
"""Verify cached overlay lifecycle, active-monitor placement, and keyboard refocus.

Native layer-shell is replaced only in this isolated test copy. Layer stacking
and actual compositor focus are covered separately in the live session.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HARNESS = '''import QtQuick
import QtQuick.Controls as Controls
import QtTest
import Quickshell
import "config"
import "services" as S
ShellRoot {
    QtObject { id: screenA; property int width: 1440; property int height: 900 }
    QtObject { id: screenB; property int width: 1440; property int height: 900 }
    QtObject {
        id: fakeApp
        property string panel: ""
        property bool nativeDialogOpen: false
        property var activeScreen: screenA
        property int activationSerial: 0
        property string settingsSection: ""
        property bool focusRunning: false
        property double focusRemaining: 1500000
        property double focusDeadline: 0
        function open(name, screen) { if (screen) activeScreen = screen; panel = name; activationSerial++; }
        function close() { panel = ""; }
        function focusStart() {} function focusPause() {} function focusReset(minutes) {}
    }
    Overlay { id: firstScreen; app: fakeApp; modelData: screenA }
    Overlay { id: secondScreen; app: fakeApp; modelData: screenB }
    TestCase {
        name: "SumiOverlay"
        when: true
        function assertTrue(condition, message) {
            if (!condition) { console.error("SUMI_OVERLAY_FAILED", message || "assertion"); Qt.exit(1); throw new Error(message); }
        }
        function assertEqual(actual, expected, message) { assertTrue(actual === expected, (message || "mismatch") + ": " + actual + " expected " + expected); }
        function isWithin(item, ancestor) {
            while (item) { if (item === ancestor) return true; item = item.parent; }
            return false;
        }
        function tryAssert(condition, timeout) {
            let elapsed = 0;
            while (!condition() && elapsed < timeout) { wait(20); elapsed += 20; }
            assertTrue(condition(), "Timed out waiting for panel");
        }
        function fits(item, container) {
            const point = item.mapToItem(container, 0, 0);
            return point.x >= -1 && point.y >= -1 && point.x + item.width <= container.width + 1 && point.y + item.height <= container.height + 1;
        }
        function visibleFocus(panel) {
            const item = firstScreen.activeFocusItem;
            assertTrue(isWithin(item, panel), "Keyboard focus remains in the menu");
            assertTrue(fits(item, panel), "Focused control fits panel: " + item + " section=" + panel.section + " size=" + panel.width + "x" + panel.height);
            let ancestor = item.parent;
            while (ancestor && ancestor !== panel) {
                if (ancestor.clip) assertTrue(fits(item, ancestor), "Focused control is scrolled into view: " + item + " in " + ancestor);
                ancestor = ancestor.parent;
            }
        }
        function buttonContentFits(item) {
            if (!item.visible) return;
            if (typeof item.clicked === "function" && item.contentItem && item.contentItem.implicitHeight > 0)
                assertTrue(item.contentItem.height >= item.contentItem.implicitHeight - 1, "Button content fits vertically: " + item.text + " " + item.contentItem.height + "/" + item.contentItem.implicitHeight);
            for (const child of item.children) buttonContentFits(child);
        }
        function noClosePrompt(panel, name) {
            const close = findChild(panel, name);
            assertTrue(close !== null && !close.activeFocus && !close.visualFocus && !close.Controls.ToolTip.visible, "Opening a menu must not focus or prompt Close");
            buttonContentFits(panel);
        }
        function savePanel(panel, name) {
            let saved = false;
            panel.grabToImage(result => { saved = result.saveToFile("/tmp/sumi-menu-" + name + ".png"); });
            tryAssert(() => saved, 2000);
        }
        function test_lifecycle() {
            // Geometry and keyboard checks are independent of animation timing.
            // The popup-motion fixture samples normal and battery transitions.
            Settings.reducedMotion = true;
            fakeApp.open("launcher", screenA);
            tryAssert(() => firstScreen.smokeItem !== null, 3000);
            wait(250);
            const first = firstScreen.smokeItem;
            assertEqual(firstScreen.shown, true);
            assertEqual(String(firstScreen.smokeScrimColor), String(Theme.scrim), "Launcher dims the entire active output");
            assertEqual(secondScreen.shown, false);
            assertEqual(secondScreen.visible, false, "Inactive monitor must not capture input or dim");
            assertEqual(firstScreen.popupShown, true);
            assertEqual(secondScreen.popupShown, false);
            assertEqual(firstScreen.width, 1440);
            assertEqual(firstScreen.height, 900);
            assertEqual(secondScreen.height, 900);
            assertTrue(first.smokeSearchItem.activeFocus, "Launcher must own typing focus");
            fakeApp.nativeDialogOpen = true; wait(40);
            assertEqual(firstScreen.visible, true, "Native dialog keeps its parent mapped");
            assertEqual(firstScreen.smokeInputWidth, 0, "Native dialog releases the pointer region");
            assertEqual(firstScreen.smokeScrimOpacity, 0, "Native dialog removes the overlay dimming");
            fakeApp.nativeDialogOpen = false; wait(40);
            assertEqual(firstScreen.smokeInputWidth, 1440, "Dismissing native dialog restores pointer input");
            first.smokeSearch = "cached query";
            fakeApp.close(); wait(230);
            assertEqual(firstScreen.visible, false);
            fakeApp.open("launcher", screenA); wait(230);
            assertTrue(firstScreen.smokeItem === first, "Launcher must be reused on reopen");
            assertEqual(first.smokeSearch, "");
            assertTrue(first.smokeSearchItem.activeFocus, "Reopening must restore typing focus");
            mouseClick(first, 10, first.height / 2);
            assertEqual(fakeApp.panel, "launcher", "Panel whitespace must not dismiss the overlay");
            fakeApp.open("settings", screenA);
            tryAssert(() => firstScreen.smokeItem !== null && firstScreen.smokeItem !== first, 3000);
            const settings = firstScreen.smokeItem;
            assertEqual(String(firstScreen.smokeScrimColor), String(Theme.scrim), "Settings uses the shared scrim");
            wait(260);
            noClosePrompt(settings, "settingsClose");
            assertEqual(firstScreen.activeFocusItem.objectName, "settingsWifi", "Controls open on Wi-Fi, without a tooltip");
            savePanel(settings, "settings");
            assertEqual(Math.round(settings.parent.x + settings.width), screenA.width - 24, "Settings right margin");
            assertTrue(settings.parent.y >= 24, "Settings top margin");
            for (let index = 0; index < 45; index++) {
                keyClick(Qt.Key_Tab);
                assertTrue(isWithin(firstScreen.activeFocusItem, settings), "Tab focus must stay in active panel");
            }
            for (let index = 0; index < 45; index++) {
                keyClick(Qt.Key_Tab, Qt.ShiftModifier);
                assertTrue(isWithin(firstScreen.activeFocusItem, settings), "Shift+Tab focus must stay in active panel");
            }
            fakeApp.close(); wait(230);
            fakeApp.open("settings", screenA); wait(230);
            assertTrue(firstScreen.smokeItem === settings, "Settings must be reused on reopen");
            for (const size of [[480, 360], [600, 440], [960, 540]]) {
                screenA.width = size[0]; screenA.height = size[1];
                for (const section of ["", "wifi", "bluetooth", "audio", "capture"]) {
                    settings.section = section;
                    settings.focusDefault(); wait(80);
                    noClosePrompt(settings, "settingsClose");
                    assertEqual(findChild(settings, "settingsBody").contentItem.contentY, 0, "Opening a subpage shows its heading");
                    assertTrue(settings.height <= size[1] - Theme.panelTop - 24, "Settings fits usable screen " + size);
                    for (let index = 0; index < 28; index++) { keyClick(Qt.Key_Tab); wait(15); visibleFocus(settings); }
                    for (let index = 0; index < 12; index++) { keyClick(Qt.Key_Tab, Qt.ShiftModifier); wait(15); visibleFocus(settings); }
                    if (size[0] === 960) {
                        settings.focusDefault(); wait(30);
                        if (section === "capture") {
                            const viewport = findChild(settings, "settingsBody");
                            assertTrue(viewport.contentItem.contentHeight <= viewport.availableHeight + 1, "Capture shows every row and subtitle at 960x540: " + viewport.contentItem.contentHeight + "/" + viewport.availableHeight);
                        }
                        savePanel(settings, section || "home-short");
                    }
                }
            }
            screenA.width = 1440; screenA.height = 900;
            settings.section = "wifi"; wait(60);
            assertTrue(settings.height < 300, "Empty Wi-Fi page does not reserve a full-height menu");
            S.Network.networks = Array.from({length: 18}, (_, index) => ({name: "Fixture network " + (index + 1), connected: false}));
            screenA.height = 440; settings.focusDefault(); wait(80);
            const settingsBody = findChild(settings, "settingsBody");
            for (let index = 0; index < 24; index++) { keyClick(Qt.Key_Tab); wait(20); visibleFocus(settings); }
            assertTrue(settingsBody.contentItem.contentY > 0, "Long device list follows Tab focus");
            S.Network.networks = [];
            screenA.height = 900;
            fakeApp.open("launcher", screenB);
            // The temporary QtQuick Window needs activation; native layer-shell uses Exclusive focus.
            secondScreen.requestActivate();
            tryAssert(() => secondScreen.smokeItem !== null, 3000);
            wait(250);
            assertEqual(firstScreen.popupShown, false);
            assertEqual(firstScreen.visible, false, "Old monitor releases its surface immediately");
            assertEqual(secondScreen.popupShown, true);
            assertTrue(secondScreen.smokeItem.smokeSearchItem.activeFocus, "Only active screen gets keyboard focus");
            secondScreen.smokeItem.smokeSearchItem.forceActiveFocus();
            keyClick(Qt.Key_Escape); wait(230);
            assertEqual(fakeApp.panel, "");
            S.Notifications.history = Array.from({length: 8}, (_, index) => ({id: 900 + index, appName: "Fixture app", summary: "Notification " + (index + 1), body: "A message with a dismiss control that must stay readable and keyboard reachable.", actions: [], popup: false, unread: false, time: new Date()}));
            for (const size of [[960, 540], [1280, 720], [1920, 1080]]) {
                screenA.width = size[0]; screenA.height = size[1];
                for (const mode of ["calendar", "media", "notifications", "help", "power"]) {
                    fakeApp.open(mode, screenA);
                    tryAssert(() => firstScreen.smokeItem !== null && firstScreen.smokeItem.kind === mode, 3000);
                    wait(260);
                    const panel = firstScreen.smokeItem;
                    noClosePrompt(panel, "dashboardClose");
                    assertEqual(String(firstScreen.smokeScrimColor), String(Theme.scrim), mode + " uses the shared scrim");
                    if (mode === "help") tryAssert(() => panel.shortcuts.length > 0, 3000);
                    assertTrue(panel.parent.x >= 24 && panel.parent.y >= 24, mode + " leading margin");
                    assertTrue(panel.parent.x + panel.width <= size[0] - 23, mode + " trailing margin");
                    assertTrue(panel.parent.y + panel.height <= size[1] - 23, mode + " bottom margin");
                    if (mode === "notifications") assertEqual(Math.round(panel.parent.x + panel.width), size[0] - 24, "History right margin");
                    else assertTrue(Math.abs(panel.parent.x + panel.width / 2 - size[0] / 2) < 1, mode + " horizontal center");
                    if (mode === "power") assertTrue(panel.height < 400, "Power menu uses its content height");
                    if (mode === "media") assertTrue(panel.height < 300, "No empty artwork placeholder in stopped media");
                    if (mode === "calendar" && size[0] === 960) {
                        const viewport = findChild(panel, "dashboardBody");
                        assertTrue(viewport.contentItem.contentHeight <= viewport.availableHeight + 1, "Compact calendar shows its complete grid and action at 960x540");
                    }
                    if (mode === "help") {
                        const viewport = findChild(panel, "dashboardBody");
                        keyClick(Qt.Key_PageDown); wait(20);
                        assertTrue(viewport.contentItem.contentY > 0, "Help supports keyboard page scrolling from initial focus");
                    }
                    if (size[0] === 960) {
                        panel.focusDefault(); wait(30); savePanel(panel, mode);
                        for (let index = 0; index < 16; index++) { keyClick(Qt.Key_Tab); wait(15); visibleFocus(panel); }
                    }
                }
            }
            fakeApp.close(); wait(230);
            Settings.reducedMotion = true;
            fakeApp.open("launcher", screenA); wait(30);
            assertEqual(firstScreen.reveal, 1);
            fakeApp.close(); wait(30);
            assertEqual(firstScreen.reveal, 0);
            assertEqual(firstScreen.visible, false);
            console.info("SUMI_OVERLAY_OK");
            Qt.quit();
        }
    }
}
'''


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    source = (repo / "shell/Overlay.qml").read_text()
    if "exclusionMode: ExclusionMode.Ignore" not in source or "exclusiveZone:" in source:
        raise SystemExit("Overlay must ignore all reserved layer zones to cover the bar")
    with tempfile.TemporaryDirectory(prefix="sumi-overlay-") as temporary:
        work = Path(temporary)
        config = work / "shell"
        shutil.copytree(repo / "shell", config)
        source = source.replace("PanelWindow {", "Window {", 1)
        source = re.sub(r"^    (screen:|anchors \{|exclusionMode:|WlrLayershell\.).*\n", "", source, flags=re.M)
        source = source.replace('    mask: Region { width: overlay.popupShown && !overlay.app.nativeDialogOpen ? overlay.width : 0; height: overlay.popupShown && !overlay.app.nativeDialogOpen ? overlay.height : 0 }', '    readonly property real smokeInputWidth: overlay.popupShown && !overlay.app.nativeDialogOpen ? overlay.width : 0')
        source = source.replace('    color: "transparent"' , '    width: modelData.width\n    height: modelData.height\n    readonly property var smokeItem: page.item\n    readonly property color smokeScrimColor: scrim.color\n    readonly property real smokeScrimOpacity: scrim.opacity\n    color: "transparent"', 1)
        (config / "Overlay.qml").write_text(source)
        launcher = config / "Launcher.qml"
        launcher.write_text(launcher.read_text().replace("    property string initialTab:", "    property alias smokeSearch: search.text\n    readonly property var smokeSearchItem: search\n    property string initialTab:", 1))
        # Deterministic read-only device fixture; no system scanner or network writes.
        (config / "services/Network.qml").write_text('''pragma Singleton
import QtQuick
import Quickshell
Singleton {
    property bool wifiAvailable: true
    property bool wifiEnabled: true
    property bool connected: false
    property string name: "Offline"
    property bool captivePortal: false
    property var networks: []
    property bool discoveryRequested: false
    property var pendingNetwork: null
    property bool connecting: false
    property string connectionError: ""
    function toggleWifi() {} function connect(network, password) {} function disconnect(network) {}
}
''')
        (config / "shell.qml").write_text(HARNESS)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, SUMI_PREVIEW="1", SUMI_STATE_DIR=str(work / "state"), SUMI_DESKTOPCTL=str(repo / "bin/desktopctl"), QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(["qs", "-p", str(config)], env=environment, capture_output=True, text=True, timeout=40)
        output = result.stdout + result.stderr
        if result.returncode or "SUMI_OVERLAY_OK" not in output or any(message in output for message in ("TypeError:", "ReferenceError:", "Failed to load configuration", "Unable to assign [undefined]", "FAIL!", "Binding loop")):
            raise SystemExit(output)
        print("PASS: every panel dims only the active screen, including its bar; anchored daily panels fit 960x540, 1280x720, 1920x1080; cached launcher/settings reused and refocused; Tab/Shift+Tab stay modal; panel whitespace; Escape; reduced motion")
        print("Native exclusion-zone and stacking verification remains compositor-specific")
        print("PASS: no initial Close focus/tooltip; actual button content fits; short menu sizing; Tab scrolls settings/device controls into view at 480x360, 600x440, 960x540; help PageDown; isolated menu renders in /tmp/sumi-menu-*.png")

if __name__ == "__main__":
    main()
