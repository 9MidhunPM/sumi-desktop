#!/usr/bin/env python3
"""Render the bar and check minimal controls, workspace dots and toast lifecycle offscreen."""
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "config"
import "services" as S
import "components" as C
ShellRoot {
    Window {
        id: materialWindow
        width: 240; height: 120; visible: true; color: "transparent"
        C.Surface { x: 10; y: 10; width: 220; height: 100; radius: 20 }
    }
    QtObject { id: screenInfo; property int width: 1440; property int height: 900; property string name: "test-output" }
    QtObject {
        id: fakeApp
        property bool barVisible: true
        property string panel: ""
        property var notificationScreen: screenInfo
        property int codexClicks: 0
        property var lastCodexScreen: null
        function toggle(name, screen) { panel = name; }
        function openIsland(section, screen, toggle) { panel = "island"; settingsSection = section; }
        property string settingsSection: ""
        function openSettings(section, screen) { settingsSection = section; panel = "settings"; }
        function close() { panel = ""; }
        function thursdayToggle() {}
        function codexToggle(screen) { codexClicks++; lastCodexScreen = screen; }
    }
    Bar { id: bar; app: fakeApp; modelData: screenInfo }
    NotificationToasts { id: toasts; app: fakeApp }
    TestCase {
        name: "SumiSurfaces"
        when: true
        function assertTrue(condition, message) {
            if (!condition) { console.error("SUMI_SURFACES_FAILED", message); Qt.exit(1); throw new Error(message); }
        }
        function checkStatusControls() {
            const battery = findChild(bar.contentItem, "barBattery");
            const settings = findChild(bar.contentItem, "barSettings");
            const audio = findChild(bar.contentItem, "barAudio");
            const wifi = findChild(bar.contentItem, "barWifi");
            assertTrue(findChild(bar.contentItem, "barCodex") === null, "Private Codex integration is absent from the public bar");
            const originalWidth = bar.width;
            let stableWidth = 0;
            for (const value of [9, 99, 100]) {
                S.Battery.device = {isPresent: true, percentage: value / 100, state: 0, timeToFull: 0, timeToEmpty: 0};
                for (const width of [568, 759, 760, 928, 1248, 1888]) {
                    bar.width = width; wait(25);
                    assertTrue(battery.visible && battery.text === value + "%", "Battery percentage stays visible at " + width);
                    if (!stableWidth) stableWidth = battery.width;
                    assertTrue(Math.abs(battery.width - stableWidth) < 0.5 && battery.width < 84, "Battery width stays stable through 100%");
                    assertTrue(battery.contentItem.width >= battery.contentItem.implicitWidth - 0.5, "Full battery percentage fits without elision");
                    for (const control of [audio, wifi, settings]) {
                        assertTrue(control && control.visible && control.text === "", "Minimal controls remain icon-only at " + width);
                        const point = control.mapToItem(bar.contentItem, 0, 0);
                        assertTrue(point.x >= bar.smokeRightEdge && point.x + control.width <= bar.width, "Right control fits its island at " + width);
                    }
                    assertTrue(bar.smokeRightIsland.width <= 230, "Right island stays compact");
                }
            }
            S.Battery.device = {isPresent: false}; wait(25);
            assertTrue(!battery.visible && settings.visible, "Settings stay reachable without battery hardware");
            S.Battery.device = {isPresent: true, percentage: 1, state: 0, timeToFull: 0, timeToEmpty: 0};
            bar.width = 1888; wait(30);
            const before = S.Audio.managerCalls;
            fakeApp.panel = "";
            mouseClick(audio, audio.width / 2, audio.height / 2, Qt.RightButton); wait(25);
            assertTrue(S.Audio.managerCalls === before + 1 && fakeApp.panel === "", "Audio right click opens only the sound manager");
            for (const pair of [[audio, "audio"], [wifi, "wifi"]]) {
                mouseClick(pair[0], pair[0].width / 2, pair[0].height / 2); wait(25);
                assertTrue(fakeApp.panel === "settings" && fakeApp.settingsSection === pair[1], "Minimal icon opens its settings page");
                fakeApp.panel = "";
            }
            mouseClick(battery, battery.width / 2, battery.height / 2);
            assertTrue(fakeApp.panel === "settings" && fakeApp.settingsSection === "", "Battery opens the standalone controls overview");
            fakeApp.panel = "";
            mouseClick(settings, settings.width / 2, settings.height / 2);
            assertTrue(fakeApp.panel === "settings", "Right settings icon opens the original control panel");
            fakeApp.panel = "";
            for (const name of ["barLauncher", "barThursday", "barBluetooth", "barNotifications", "trayOverflow"])
                assertTrue(findChild(bar.contentItem, name) === null, "Removed clutter stays absent: " + name);
            assertTrue(typeof bar.trayItems === "undefined" && typeof bar.activateTray === "undefined", "Bar no longer owns a system tray");
            bar.width = originalWidth; wait(30);
        }
        function checkSides(width) {
            assertTrue(bar.height === 34, "Bar reservation remains34px");
            assertTrue(bar.smokeLeftIsland.height === 32 && bar.smokeRightIsland.height === 32, "Side glass islands retain their height");
            assertTrue(bar.smokeLeftEdge < bar.smokeRightEdge && bar.centerRoom > 100, "Side controls leave centered island space at " + width);
            const pixels = grabImage(bar.contentItem);
            assertTrue(pixels.alpha(Math.floor(bar.width / 2), 16) === 0, "Center belongs to its separate native surface");
            for (let id = 1; id <= 5; id++) checkWorkspaceDot(findChild(bar.contentItem, "workspaceButton" + id), id);
        }
        function checkAnimatedBar() {
            const content = findChild(bar.contentItem, "barContent");
            assertTrue(content !== null, "Animated bar content exists");
            Settings.reducedMotion = false;
            const closing = [];
            fakeApp.barVisible = false;
            for (let frame = 0; frame < 12; frame++) { wait(16); closing.push(bar.reveal); }
            tryCompare(bar, "reveal", 0, 500);
            assertTrue(closing.some(value => value > 0 && value < 1), "Bar exit has actual intermediate frames");
            assertTrue(!bar.visible && Math.abs(content.mapToItem(bar.contentItem, 0, 0).y + Theme.barHeight + 6) <= 0.5, "Hidden bar slides fully above the screen");
            const opening = [];
            fakeApp.barVisible = true;
            for (let frame = 0; frame < 12; frame++) { wait(16); opening.push(bar.reveal); }
            tryCompare(bar, "reveal", 1, 500);
            assertTrue(opening.some(value => value > 0 && value < 1), "Bar entrance has actual intermediate frames");
            assertTrue(bar.visible && Math.abs(content.mapToItem(bar.contentItem, 0, 0).y) <= 0.5, "Shown bar settles at its original position");
            Settings.reducedMotion = true;
        }
        function checkWorkspaceDot(button, id) {
            const dot = findChild(button, "workspaceDot" + id);
            assertTrue(dot && dot.visible, "Workspace " + id + " has one indicator");
            assertTrue(findChild(button, "workspaceNumber" + id) === null && findChild(button, "workspaceOccupancy" + id) === null, "Workspace has no number or per-window dot row");
            const local = dot.mapToItem(button, 0, 0);
            const inBar = dot.mapToItem(bar.contentItem, 0, 0);
            assertTrue(Math.abs(local.x + dot.width / 2 - button.width / 2) <= 0.5 && Math.abs(local.y + dot.height / 2 - button.height / 2) <= 0.5, "Workspace dot is centered in its hit target");
            assertTrue(Math.abs(inBar.y + dot.height / 2 - bar.height / 2) <= 0.5, "Workspace dot is centered in the bar");
            assertTrue(dot.height === 6 && dot.width === (button.entry.active ? 16 : 6), "Active workspace becomes a short pill");
            assertTrue(button.width === (button.tight ? 20 : 22), "Workspace target width is independent of window count");
            return dot;
        }
        function checkWindowDots(id, count, urgent) {
            const button = findChild(bar.contentItem, "workspaceButton" + id);
            assertTrue(button !== null, "Workspace " + id + " exists");
            const dot = checkWorkspaceDot(button, id);
            assertTrue(button.windowCount === count && button.summary.indexOf(count ? count + " window" : "empty") >= 0, "Workspace preserves window-count accessibility");
            assertTrue(String(dot.color) === String(urgent ? Theme.accentWarn : button.entry.active ? Theme.accentBlue : Theme.textMain), "Dot follows urgency, selection and theme");
            const opacity = button.entry.active || urgent ? 1 : count ? 0.78 : 0.28;
            assertTrue(Math.abs(dot.opacity - opacity) < 0.01, "Inactive empty and occupied workspaces have distinct emphasis");
        }
        function noWorkspaceAppIcons(item) {
            assertTrue(!item.objectName.startsWith("workspaceAppIcon"), "Workspaces retain only their minimal indicators");
            for (const child of item.children) noWorkspaceAppIcons(child);
        }
        function test_surfaces() {
            Settings.reducedMotion = true;
            S.Media.playing = true;
            wait(200);
            const material = grabImage(materialWindow.contentItem);
            const centerAlpha = material.alpha(120, 60);
            assertTrue(centerAlpha > 150 && centerAlpha < 205, "Glass retains a translucent body rather than an opaque panel");
            assertTrue(material.alpha(120, 14) > centerAlpha, "Upper reflection gives glass a visible highlight");
            assertTrue(material.alpha(10, 10) === 0 && material.alpha(4, 4) === 0, "Rounded glass leaves its corners and surrounding area transparent");
            assertTrue(Theme.scrim.a < 0.55, "Monitor dimmer stays below the overlay blur threshold");
            assertTrue(bar.workspaceEntries.length === 5, "Exactly five base workspace entries exist");
            bar.monitor = {activeWorkspace: {id: 2}};
            assertTrue(bar.activeWorkspaceId === 2, "Workspace highlight follows this monitor");
            const baseButton = findChild(bar.contentItem, "workspaceButton2");
            const occupancy = findChild(bar.contentItem, "workspaceDot2");
            assertTrue(occupancy !== null, "Workspace dot delegate exists");
            for (let update = 0; update < 24; update++) {
                bar.workspaces = [null, {id: 2, toplevels: {values: [{}]}, urgent: true}]; wait(5);
                checkWindowDots(2, 1, true);
                bar.workspaces = [null, {id: 2, toplevels: null}]; wait(5);
                checkWindowDots(2, 0, false);
                bar.workspaces = []; wait(5);
                assertTrue(findChild(bar.contentItem, "workspaceDot2") === occupancy && findChild(bar.contentItem, "workspaceButton2") === baseButton, "Workspace churn preserves base delegate identities");
            }
            const sameClassWindows = Array.from({length: 3}, (_, index) => ({wayland: {appId: "FixtureEditor"}, lastIpcObject: {address: "0x" + (100 + index)}}));
            const otherWindow = {wayland: {appId: "FixtureOther"}};
            for (const windows of [[], [null]]) {
                bar.workspaces = [{id: 8, toplevels: {values: windows}}]; wait(20);
                assertTrue(bar.additionalWorkspaces.length === 0 && findChild(bar.contentItem, "workspaceButton8") === null, "Higher workspace requires a real window");
            }
            bar.workspaces = [{id: 8, toplevels: {values: [sameClassWindows[0]]}}]; wait(30);
            assertTrue(bar.additionalWorkspaces.length === 1 && findChild(bar.contentItem, "workspaceButton8") !== null, "Occupied workspace8 appears dynamically");
            checkWindowDots(8, 1, false);
            bar.workspaces = [{id: 8, toplevels: null}]; wait(30);
            assertTrue(bar.additionalWorkspaces.length === 0 && findChild(bar.contentItem, "workspaceButton8") === null, "Emptied workspace8 disappears");
            for (let id = 6; id <= 10; id++) assertTrue(findChild(bar.contentItem, "workspaceButton" + id) === null, "Empty higher workspace " + id + " is absent");
            bar.workspaces = [];
            const occupiedWorkspaces = [
                {id: 2, name: "2", toplevels: {values: sameClassWindows}},
                {id: 8, name: "8", toplevels: {values: [otherWindow]}},
                {id: -98, name: "special:magic", toplevels: {values: [sameClassWindows[0]]}}
            ];
            bar.workspaces = occupiedWorkspaces; wait(50);
            assertTrue(bar.workspaceEntries[1].windowCount === 3, "Three windows of the same application remain three windows");
            checkWindowDots(2, 3, false);
            for (const width of [600, 960, 1280, 1920]) {
                bar.width = width - 32; wait(100);
                checkSides(width);
                assertTrue(bar.additionalWorkspaces.length === 1 && bar.additionalWorkspaces[0].id === 8, "Only occupied higher workspace remains in model");
                assertTrue(bar.inlineExtraWorkspaces.some(entry => entry.id === 8) || bar.workspaceMenuEntries.some(entry => entry.id === 8), "Occupied workspace8 remains reachable at " + width);
                for (const id of [6, 7, 9, 10]) assertTrue(findChild(bar.contentItem, "workspaceButton" + id) === null, "Empty workspace " + id + " stays absent with occupied8");
                checkWindowDots(2, 3, false);
                for (const id of [1, 3, 4, 5]) checkWindowDots(id, 0, false);
                if (bar.inlineExtraWorkspaces.some(entry => entry.id === 8)) checkWindowDots(8, 1, false);
                noWorkspaceAppIcons(bar.smokeLeftIsland);
                if ([600, 1280, 1920].indexOf(width) >= 0) grabImage(bar.contentItem).save("/tmp/sumi-bar-" + width + ".png");
            }
            checkStatusControls();
            const workspaceOverflow = findChild(bar.contentItem, "workspaceOverflow");
            assertTrue(workspaceOverflow.text === "" && workspaceOverflow.iconName === "more-horizontal", "Workspace overflow never shows a +count badge");
            const originalTheme = Theme.document;
            Theme.document = Object.assign({}, originalTheme, {colors: Object.assign({}, originalTheme.colors || {}, {accentBlue: "#36b7a5"})});
            wait(80);
            checkWindowDots(2, 3, false);
            checkWindowDots(8, 1, false);
            Theme.document = originalTheme; wait(80);
            checkWindowDots(2, 3, false);
            for (const count of [7, 2, 0, 3]) {
                bar.workspaces = [{id: 2, toplevels: {values: Array.from({length: count}, (_, index) => ({wayland: {appId: "FixtureEditor"}, lastIpcObject: {address: "0x" + (200 + index)}}))}}]; wait(30);
                checkWindowDots(2, count, false);
                assertTrue(findChild(bar.contentItem, "workspaceButton2") === baseButton && findChild(bar.contentItem, "workspaceDot2") === occupancy, "Count changes preserve the base workspace and single indicator");
                noWorkspaceAppIcons(baseButton);
            }
            bar.workspaces = []; wait(40);
            checkAnimatedBar();
            fakeApp.barVisible = false; wait(30);
            assertTrue(!bar.visible, "Reduced-motion bar hides immediately");
            fakeApp.barVisible = true; wait(30);
            assertTrue(bar.visible, "Bar reopens");
            const note = {id: 1, appName: "Test", summary: "First", body: "Toast lifecycle", actions: [], popup: true};
            S.Notifications.history = [note]; wait(100);
            assertTrue(toasts.visible && toasts.smokeCount === 1, "Notification appears");
            S.Notifications.history = [Object.assign({}, note, {summary: "Updated"})]; wait(80);
            assertTrue(toasts.smokeCount === 1 && toasts.smokeFirst.summary === "Updated", "Replace-id updates existing toast");
            S.Desktop.lastError = "The test action failed"; wait(80);
            assertTrue(toasts.smokeCount === 2 && toasts.smokeFirst.error, "Action errors are visible and prioritized");
            S.Desktop.lastError = ""; wait(80);
            assertTrue(toasts.smokeCount === 1, "Action error can be dismissed");
            fakeApp.panel = "settings"; wait(30);
            assertTrue(!toasts.visible, "Toasts yield to open panels");
            fakeApp.panel = ""; wait(30);
            assertTrue(toasts.visible, "Pending toast returns after panel closes");
            Settings.reducedMotion = false;
            S.Notifications.history = []; wait(400);
            assertTrue(!toasts.visible && toasts.smokeCount === 0, "Final removal completes exit animation");
            console.info("SUMI_SURFACES_OK"); Qt.quit();
        }
    }
}
'''


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-surfaces-") as temporary:
        work = Path(temporary)
        config = work / "shell"
        shutil.copytree(repo / "shell", config)
        media = config / "services/Media.qml"
        media.write_text(media.read_text().replace("readonly property bool playing: player ? player.isPlaying : false", "property bool playing: false"))
        battery = config / "services/Battery.qml"
        battery.write_text(battery.read_text().replace("readonly property var device: Up.UPower.displayDevice", "property var device: ({isPresent: true, percentage: 1, state: 0, timeToFull: 0, timeToEmpty: 0})"))
        for name, command in (("Audio", "audio-manager"),):
            service = config / "services" / (name + ".qml")
            service.write_text(service.read_text().replace('function openManager(): void { Desktop.action("' + command + '", []); }', 'property int managerCalls: 0\n    function openManager(): void { managerCalls++; }'))
        data = work / "data"
        data.mkdir()
        for filename in ("Bar.qml", "NotificationToasts.qml"):
            path = config / filename
            source = path.read_text().replace("PanelWindow {", "Window {", 1)
            source = re.sub(r"    mask: Region \{.*?^    \}\n", "", source, flags=re.M | re.S)
            source = re.sub(r"^    (screen:|anchors \{|margins \{|exclusiveZone:|WlrLayershell\.).*\n", "", source, flags=re.M)
            source = re.sub(r"^    implicit(Width|Height):", lambda match: "    " + match[1].lower() + ":", source, flags=re.M)
            if filename == "Bar.qml":
                source = re.sub(r"    readonly property var monitor:.*\n", "    property var monitor: null\n", source)
                source = re.sub(r"    DynamicIsland \{.*?^    \}\n", "", source, flags=re.M | re.S)
                source = source.replace("readonly property var workspaces: Hyprland.workspaces.values", "property var workspaces: []")
                source = source.replace('    color: "transparent"', '''    width: 1440
    readonly property real smokeLeftEdge: leftIsland.x + leftIsland.width
    readonly property real smokeRightEdge: rightIsland.x
    readonly property var smokeLeftIsland: leftIsland
    readonly property var smokeRightIsland: rightIsland
    color: "transparent"''', 1)
            else:
                source = source.replace('    color: "transparent"', '''    readonly property int smokeCount: toastModel.count
    readonly property var smokeFirst: toastModel.count ? toastModel.get(0).entry : ({})
    color: "transparent"''', 1)
            path.write_text(source)
        (config / "shell.qml").write_text(HARNESS)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, SUMI_PREVIEW="1", SUMI_STATE_DIR=str(work / "state"), QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime), XDG_DATA_HOME=str(data))
        result = subprocess.run(["qs", "-p", str(config)], env=environment, capture_output=True, text=True, timeout=20)
        output = result.stdout + result.stderr
        if result.returncode or "SUMI_SURFACES_OK" not in output or any(message in output for message in ("TypeError:", "ReferenceError:", "Failed to load configuration", "Unable to assign [undefined]", "FAIL!", "Binding loop")):
            raise SystemExit(output)
        for width in (600, 1280, 1920):
            image = Path(f"/tmp/sumi-bar-{width}.png")
            header = image.read_bytes()[:24]
            if header[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", header[16:24]) != (width - 32, 34):
                raise SystemExit(f"Invalid offscreen bar render: {image}")
        print("PASS:34px bar reservation; separate center; workspace dots/active pill and overflow; minimal right controls and fixed-width battery; click routes; glass pixels; bar motion; toast lifecycle")
        print("Offscreen renders: /tmp/sumi-bar-600.png /tmp/sumi-bar-1280.png /tmp/sumi-bar-1920.png")
        print("Native layer placement and popup menu grabs require compositor validation")


if __name__ == "__main__":
    main()
