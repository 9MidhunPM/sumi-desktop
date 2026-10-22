#!/usr/bin/env python3
"""Exercise quick settings with real pointer/key events and controlled services."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

DESKTOP = '''pragma Singleton
import QtQuick
import Quickshell
Singleton {
    property bool preview: false
    property var requests: []
    function action(name, args, callback) { requests = requests.concat([{name: name, args: args, callback: callback}]); }
    function respond(name, ok, result, error) {
        const index = requests.findIndex(item => item.name === name && typeof item.callback === "function");
        if (index < 0) throw new Error("No pending " + name);
        const request = requests[index]; requests = requests.filter((item, i) => i !== index);
        request.callback(ok, result, error || "");
    }
}
'''
NETWORK = '''pragma Singleton
import QtQuick
import Quickshell
Singleton {
    property bool wifiAvailable: true
    property bool wifiEnabled: true
    property bool connected: true
    property string name: "Home Wi-Fi"
    property bool captivePortal: false
    property bool connecting: false
    property string connectionError: ""
    property var pendingNetwork: null
    property var networks: []
    property int toggles: 0
    function toggleWifi() { toggles++; wifiEnabled = !wifiEnabled; }
    function connect(network, password) {}
    function disconnect(network) {}
}
'''
AUDIO = '''pragma Singleton
import QtQuick
import Quickshell
Singleton {
    property bool hasOutput: true
    property bool hasInput: true
    property string outputName: "Fixture headphones"
    property string inputName: "Fixture microphone"
    property real volume: 0.4
    property real sourceVolume: 0.3
    property bool muted: false
    property bool sourceMuted: false
    property var sinks: []
    property var sources: []
    property var sink: null
    property var source: null
    property int muteClicks: 0
    function setVolume(value) { volume = value; }
    function setSourceVolume(value) { sourceVolume = value; }
    function toggleMute() { muteClicks++; muted = !muted; }
    function toggleSourceMute() { sourceMuted = !sourceMuted; }
    function selectSink(node) {}
    function selectSource(node) {}
    function openManager() { Desktop.action("audio-manager", []); }
}
'''
HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "config"
import "services" as S
ShellRoot {
    QtObject { id: screenInfo; property int width: 1280; property int height: 1080 }
    QtObject {
        id: fakeApp
        property var activeScreen: screenInfo
        property string panel: "settings"
        property string settingsSection: ""
        property int closed: 0
        function close() { closed++; panel = ""; }
        function open(name, screen) { panel = name; }
    }
    QtObject {
        id: adapter
        property bool enabled: true
        property bool discovering: false
        property var devices: ({values: []})
    }
    QtObject { id: nearby; property string name: "A nearby"; property string address: "03"; property bool connected: false; property bool paired: false }
    QtObject { id: paired; property string name: "B paired"; property string address: "02"; property bool connected: false; property bool paired: true }
    QtObject { id: connected; property string name: "Z connected"; property string address: "01"; property bool connected: true; property bool paired: true }
    Window {
        id: win
        width: screenInfo.width; height: screenInfo.height; visible: true
        QuickSettings { id: settings; app: fakeApp; anchors.centerIn: parent }
        TestCase {
            name: "SumiQuickSettings"
            when: win.visible
            function assertTrue(condition, message) {
                if (!condition) { console.error("SUMI_QUICK_SETTINGS_FAILED", message); Qt.exit(1); throw new Error(message); }
            }
            function control(name) { const item = findChild(settings, name); assertTrue(item !== null, "Control exists: " + name); return item; }
            function reveal(item) { item.forceActiveFocus(Qt.TabFocusReason); wait(30); }
            function click(item, button) { reveal(item); mouseClick(item, item.width / 2, item.height / 2, button || Qt.LeftButton); wait(30); }
            function test_controls() {
                Settings.reducedMotion = true;
                S.Bluetooth.adapter = adapter;
                adapter.devices = {values: [nearby, paired, connected]};
                wait(100);
                assertTrue(!control("settingsBrightness").enabled, "Brightness starts disabled until an actual reading");
                S.Desktop.respond("brightness-get", false, {}, "No backlight");
                assertTrue(!settings.brightnessReady && settings.controlError === "No backlight", "Read errors never invent a brightness percentage");
                settings.readBrightness();
                S.Desktop.respond("brightness-get", true, {percent: 42});
                S.Desktop.respond("night-light-get", true, {available: true, active: false, temperature: null});
                wait(30);
                assertTrue(settings.brightnessReady && control("settingsBrightness").enabled && settings.brightness === 42, "Validated brightness enables its slider");
                settings.controlError = "";
                assertTrue(control("settingsOutputName").text === "Fixture headphones", "Selected output is visible");
                const wifi = control("settingsWifi");
                const wifiToggle = control("settingsWifiToggle");
                click(wifiToggle);
                assertTrue(S.Network.toggles === 1 && settings.section === "", "Radio secondary pointer toggles exactly once without opening its parent");
                wifiToggle.forceActiveFocus(Qt.TabFocusReason); keyClick(Qt.Key_Return); wait(30);
                assertTrue(S.Network.toggles === 2 && settings.section === "", "Radio toggle is keyboard reachable and independent");
                click(wifi);
                assertTrue(settings.section === "wifi", "Radio tile retains device-page navigation");
                settings.section = ""; wait(30);
                click(control("settingsBluetoothToggle"));
                assertTrue(!adapter.enabled && settings.section === "", "Bluetooth toggle remains in control center");
                adapter.enabled = true;
                assertTrue(S.Bluetooth.sortedDevices.map(item => item.name).join("|") === "Z connected|B paired|A nearby", "Connected then paired devices precede nearby devices");
                nearby.connected = true; wait(30);
                assertTrue(S.Bluetooth.sortedDevices[0] === nearby, "Bluetooth order reacts to connection changes and sorts names within a group");
                const closedBefore = fakeApp.closed;
                click(control("settingsBluetooth"), Qt.RightButton);
                assertTrue(fakeApp.closed === closedBefore + 1 && settings.section === "" && S.Desktop.requests.slice(-1)[0].name === "bluetooth-manager", "Bluetooth right-click opens the manager without navigating or toggling");
                fakeApp.panel = "settings";
                const muteBefore = S.Audio.muteClicks;
                click(control("settingsMute"), Qt.RightButton);
                assertTrue(S.Audio.muteClicks === muteBefore && S.Desktop.requests.slice(-1)[0].name === "audio-manager", "Sound right-click opens mixer without muting");
                fakeApp.panel = "settings";
                const nightLight = control("settingsNightLight");
                click(nightLight);
                assertTrue(settings.nightLightBusy && !settings.nightLight && !nightLight.enabled, "Night light waits for actual completion and blocks duplicate toggles");
                S.Desktop.respond("night-light", true, {available: true, active: true, temperature: 4200});
                assertTrue(settings.nightLight && !settings.nightLightBusy, "Night light displays confirmed state");
                click(nightLight);
                S.Desktop.respond("night-light", false, {}, "Temperature rejected");
                S.Desktop.respond("night-light-get", true, {available: true, active: true, temperature: 4200});
                assertTrue(settings.nightLight && settings.controlError === "Temperature rejected", "Failed toggle restores observed state and visible error");
                settings.section = "audio"; wait(30);
                assertTrue(control("settingsInputName").text === "Fixture microphone", "Selected microphone is visible");
                const gain = control("settingsInputVolume");
                reveal(gain); keyClick(Qt.Key_Right); wait(30);
                assertTrue(S.Audio.sourceVolume > 0.3, "Microphone level has real keyboard control");
                S.Audio.hasInput = false; S.Audio.hasOutput = false; wait(30);
                assertTrue(!gain.enabled && !control("settingsOutputVolume").enabled, "Missing devices disable matching sliders");
                click(control("settingsAudioManager"));
                assertTrue(S.Desktop.requests.slice(-1)[0].name === "audio-manager", "Keyboard-visible mixer alternative launches same action");
                fakeApp.panel = "settings"; settings.section = "capture"; wait(30);
                assertTrue(!control("settingsRecordStart").enabled, "Recording status gates Start");
                S.Desktop.respond("record", true, {recording: true, file: "/tmp/recording.mp4"});
                wait(30);
                assertTrue(control("settingsRecordStop").visible && !control("settingsRecordStart").visible, "Active recording exposes Stop only");
                click(control("settingsRecordStop"));
                S.Desktop.respond("record", true, {recording: false, file: "/tmp/recording.mp4"});
                wait(30);
                assertTrue(!settings.recording && control("settingsRecordStart").visible && !control("settingsRecordStop").visible, "Stop completion returns to Start");
                const requestCount = S.Desktop.requests.length; wait(400);
                assertTrue(S.Desktop.requests.length === requestCount, "Recorder adds no recurring polling");
                settings.section = "";
                for (const size of [[480, 360], [600, 440], [1280, 720]]) {
                    screenInfo.width = size[0]; screenInfo.height = size[1]; wait(40);
                    assertTrue(settings.width <= size[0] - 48 && settings.height <= size[1] - Theme.panelTop - 24, "Settings fit short logical display " + size);
                    reveal(wifiToggle);
                    const p = wifiToggle.mapToItem(settings, 0, 0);
                    assertTrue(p.y >= 0 && p.y + wifiToggle.height <= settings.height, "Radio toggle scrolls into view " + size);
                    keyClick(Qt.Key_Tab); wait(20);
                    assertTrue(win.activeFocusItem !== wifiToggle, "Secondary toggle does not trap Tab focus");
                }
                // The singleton outlives this fixture tree during shutdown.
                S.Bluetooth.adapter = null;
                console.info("SUMI_QUICK_SETTINGS_OK"); Qt.quit();
            }
        }
    }
}
'''


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-quick-settings-") as temporary:
        work = Path(temporary)
        config = work / "shell"
        shutil.copytree(repo / "shell", config)
        for name, source in (("Desktop", DESKTOP), ("Network", NETWORK), ("Audio", AUDIO)):
            (config / "services" / f"{name}.qml").write_text(source)
        (config / "services/Notifications.qml").write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nSingleton { function toggleDnd() {} }\n')
        bluetooth = config / "services/Bluetooth.qml"
        bluetooth.write_text(bluetooth.read_text().replace("readonly property var adapter: Bt.Bluetooth.defaultAdapter", "property var adapter: null"))
        (config / "shell.qml").write_text(HARNESS)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, SUMI_PREVIEW="1", SUMI_STATE_DIR=str(work / "state"), QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(["qs", "-p", str(config)], env=environment, capture_output=True, text=True, timeout=20)
        output = result.stdout + result.stderr
        if result.returncode or "SUMI_QUICK_SETTINGS_OK" not in output or any(message in output for message in ("TypeError:", "ReferenceError:", "Failed to load configuration", "Unable to assign [undefined]", "FAIL!", "Binding loop")):
            raise SystemExit(output)
        print("PASS: independent pointer/keyboard radio toggles; Bluetooth ordering; manager right-clicks and buttons; selected devices and microphone gain; unavailable hardware; brightness read errors; confirmed night light; recording state without polling; short-display focus")


if __name__ == "__main__":
    main()
