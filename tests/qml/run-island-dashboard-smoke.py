#!/usr/bin/env python3
"""Exercise the real dashboard against deterministic, mutation-free services."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "components"
import "services" as S
ShellRoot {
    QtObject {
        id: fakeApp
        property bool focusRunning: false
        property double focusDeadline: 0
        property double focusRemaining: 1500000
        function focusStart() { focusRunning = true; focusDeadline = Date.now() + focusRemaining; }
        function focusPause() { focusRunning = false; }
        function focusReset(minutes) { focusRunning = false; focusRemaining = minutes * 60000; }
    }
    FloatingWindow {
        id: window
        visible: true
        implicitWidth: 640
        implicitHeight: 520
        color: "black"
        IslandDashboard {
            id: dashboard
            anchors.fill: parent
            anchors.margins: 16
            app: fakeApp
            active: true
            onSectionRequested: section => dashboard.section = section
        }
        TestCase {
            name: "IslandDashboard"
            when: true
            function check(value, message) { if (!value) { console.error("ISLAND_DASHBOARD_FAILED", message); Qt.exit(1); throw new Error(message); } }
            function test_dashboard() {
                wait(350);
                check(dashboard.section === "home", "Expected dashboard.section");
                check(!fakeApp.focusRunning, "initial focus false");
                findChild(dashboard, "islandDashboardFocus").clicked();
                check(fakeApp.focusRunning, "focus start works");
                findChild(dashboard, "islandTabInbox").clicked();
                check(dashboard.section === "inbox", "Expected dashboard.section");
                wait(350);
                check(S.Notifications.unread === 0, "Expected S.Notifications.unread");
                S.Notifications.history = [{id: 2, appName: "Other app", summary: "New message", body: "Keep the selected page", time: new Date(), unread: true, actions: []}];
                dashboard.section = "controls";
                wait(350);
                check(S.Notifications.unread === 1, "Expected S.Notifications.unread");
                check(findChild(dashboard, "islandDashboardBrightness").enabled, "brightness enabled");
                check(dashboard.section === "controls", "Expected dashboard.section");
                findChild(dashboard, "islandTabMedia").clicked();
                check(dashboard.section === "media", "Expected dashboard.section");
                dashboard.anchors.fill = null; dashboard.width = 320; dashboard.height = 488;
                wait(100);
                check(dashboard.width === 320, "narrow width");
                dashboard.section = "controls";
                wait(350);
                const controlsContent = findChild(dashboard, "islandControlsContent");
                check(controlsContent.width <= dashboard.width, "Controls content fits viewport");
                for (const group of controlsContent.children) {
                    if (!group.children) continue;
                    for (const button of group.children)
                        if (button.visible && typeof button.text === "string" && typeof button.clicked === "function")
                            check(button.x + button.width <= controlsContent.width + 1, "Wrapped controls stay within viewport");
                }
                findChild(dashboard, "islandControlsScroll").contentItem.contentY = 0;
                wait(100);
                const level = findChild(dashboard, "islandDashboardBrightness");
                const pixels = grabImage(dashboard);
                const origin = level.mapToItem(dashboard, 0, 0);
                check(pixels.red(Math.floor(origin.x + level.width * .25), Math.floor(origin.y + level.height * .75)) > 200, "Vertical brightness fill renders white");
                check(pixels.red(Math.floor(origin.x + level.width / 2), Math.floor(origin.y + level.height * .35)) < 100, "Vertical brightness track renders charcoal");
                findChild(dashboard, "islandDashboardRecord").forceActiveFocus(Qt.OtherFocusReason);
                wait(100);
                check(findChild(dashboard, "islandControlsScroll").contentItem.contentY > 0, "Keyboard focus reveals lower controls");
                const finalControl = findChild(dashboard, "islandControlMore");
                finalControl.forceActiveFocus(Qt.OtherFocusReason);
                wait(100);
                const finalY = finalControl.mapToItem(findChild(dashboard, "islandControlsScroll").contentItem, 0, 0).y;
                check(finalY >= -1 && finalY + finalControl.height <= findChild(dashboard, "islandControlsScroll").height + 1, "Final narrow footer control is reachable");
                dashboard.width = 280;
                dashboard.section = "home";
                wait(250);
                const summary = findChild(dashboard, "islandHomeSummary");
                check(summary.width <= 280, "Compact Home fits 280 pixels");
                for (const tile of summary.children)
                    check(tile.x + tile.width <= summary.width + 1, "Compact Home modules fit viewport");
                dashboard.section = "media";
                wait(250);
                const title = findChild(dashboard, "islandDashboardTrackTitle");
                check(title.mapToItem(dashboard, 0, 0).x + title.width <= 281, "Compact media title stays within viewport");
                dashboard.section = "home";
                wait(250);
                findChild(dashboard, "islandTabHome").forceActiveFocus(Qt.OtherFocusReason);
                keyClick(Qt.Key_Tab, Qt.ControlModifier);
                wait(350);
                check(dashboard.section === "inbox", "Ctrl Tab from tabbar changes page");
                keyClick(Qt.Key_Tab, Qt.ControlModifier | Qt.ShiftModifier);
                wait(250);
                check(dashboard.section === "home", "Ctrl Shift Tab returns to previous page");
                const captureDir = Quickshell.env("SUMI_DASHBOARD_CAPTURE_DIR");
                if (captureDir) {
                    dashboard.width = 280;
                    for (const page of ["home", "inbox", "media"]) {
                        dashboard.section = page;
                        wait(250);
                        grabImage(dashboard).save(captureDir + "/island-" + page + "-narrow.png");
                    }
                    dashboard.width = 608;
                    for (const page of ["home", "inbox", "media", "controls"]) {
                        dashboard.section = page;
                        wait(350);
                        grabImage(dashboard).save(captureDir + "/island-" + page + ".png");
                    }
                }
                dashboard.active = false;
                S.Notifications.history = S.Notifications.history.map(entry => Object.assign({}, entry, {unread: true}));
                dashboard.section = "inbox";
                wait(150);
                check(S.Notifications.unread === 1, "Expected S.Notifications.unread");
                console.info("ISLAND_DASHBOARD_OK");
                Qt.quit();
            }
        }
    }
}
'''

STUBS = {
    'Notifications': '''property var history: [{id: 1, appName: "Fixture", summary: "A notification", body: "A body", time: new Date(), unread: true, actions: ["Reply"]}]
readonly property int count: history.length
readonly property int unread: history.filter(entry => entry.unread).length
property bool dnd: false
function toggleDnd() { dnd = !dnd; }
function markEntriesRead(ids) { history = history.map(entry => Object.assign({}, entry, {unread: ids.indexOf(entry.id) >= 0 ? false : entry.unread})); }
function dismissPopup(id) { history = history.map(entry => entry.id === id ? Object.assign({}, entry, {actions: []}) : entry); }
function invoke(id, index) {}
''',
    'Brightness': '''property real percent: 42
property bool ready: true
property bool available: true
property bool loading: false
property bool busy: false
property string error: ""
function refresh() {}
function setPercent(value) { percent = value; }
''',
    'Recording': '''property bool ready: true
property bool recording: false
property bool busy: false
property string file: ""
property string error: ""
function refresh() {}
function start() { recording = true; }
function stop() { recording = false; }
''',
    'NightLight': '''property bool available: true
property bool active: false
property bool busy: false
property string error: ""
function refresh() {}
function toggle() { active = !active; }
''',
    'Battery': '''property bool available: true
property real percent: 65
property bool charging: false
property string profile: "balanced"
property bool performanceAvailable: true
property string timeLabel: "3h 12m remaining"
function setProfile(value) { profile = value; }
''',
    'Audio': '''property bool hasOutput: true
property bool hasInput: true
property real volume: .5
property bool muted: false
property bool sourceMuted: false
function setVolume(value) { volume = value; }
function toggleMute() { muted = !muted; }
function toggleSourceMute() { sourceMuted = !sourceMuted; }
''',
    'Network': '''property bool wifiAvailable: true
property bool wifiEnabled: true
property string name: "Fixture Wi-Fi"
function toggleWifi() { wifiEnabled = !wifiEnabled; }
''',
    'Bluetooth': '''property bool available: true
property bool enabled: true
function toggle() { enabled = !enabled; }
''',
    'IslandMedia': '''property var player: null
property bool available: false
property bool playing: false
property string title: "Nothing playing"
property string artist: ""
property string artUrl: ""
function meaningful(player) { return true; }
function select(player) {}
function previous() {}
function next() {}
function toggle() {}
function seek(value) {}
''',
    'Media': 'property var players: []\n',
}


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sumi-island-dashboard-') as temporary:
        work = Path(temporary)
        shutil.copytree(repo / 'shell/components', work / 'components')
        shutil.copytree(repo / 'shell/config', work / 'config')
        shutil.copytree(repo / 'shell/assets', work / 'assets')
        services = work / 'services'
        services.mkdir()
        (services / 'qmldir').write_text(''.join(f'singleton {name} {name}.qml\n' for name in STUBS))
        for name, body in STUBS.items():
            (services / f'{name}.qml').write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nSingleton {\n' + body + '}\n')
        (work / 'shell.qml').write_text(HARNESS)
        runtime = work / 'runtime'
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(runtime), SUMI_PREVIEW='1')
        result = subprocess.run(['qs', '-p', str(work)], env=environment, text=True, capture_output=True, timeout=18)
        output = result.stdout + result.stderr
        if result.returncode or 'ISLAND_DASHBOARD_OK' not in output or any(message in output for message in ['TypeError:', 'ReferenceError:', 'Unable to assign [undefined]', 'Failed to load configuration', 'FAIL!']):
            raise SystemExit(output)
        print('PASS: dashboard focus controls; tabs; visible-only unread handling; no incoming tab switching; inactive Inbox; narrow layout')


if __name__ == '__main__':
    main()
