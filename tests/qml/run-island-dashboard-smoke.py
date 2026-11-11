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
    Component {
        id: compactPreview
        IslandNotificationPreview {
            property int dismissals: 0
            width: 280; height: 180
            onDismissRequested: dismissals++
        }
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
                check(findChild(dashboard, "islandUsageValue-cpu").text === "27%", "Home shows observed CPU usage");
                check(findChild(dashboard, "islandUsageValue-memory").text === "6.0 GB", "Home shows actual RAM consumption");
                check(findChild(dashboard, "islandUsageValue-storage").text === "128 GB", "Home shows actual storage consumption");
                S.SystemStats.cpuAvailable = false;
                check(findChild(dashboard, "islandUsageValue-cpu").text === "Unavailable", "Unavailable CPU never appears as fake zero");
                S.SystemStats.cpuAvailable = true;
                check(findChild(dashboard, "islandDashboardFocus") === null && findChild(dashboard, "islandHomeRecord") === null, "Usage replaces prominent focus and record tiles");
                const preview = compactPreview.createObject(window.contentItem, {entry: {
                    id: 99, appName: "Long fixture", summary: "A long message",
                    body: Array(18).fill("A line of notification content.").join(" "), time: new Date(),
                    actions: ["First", "Second", "Third", "Last action"]
                }});
                wait(100);
                const previewScroll = findChild(preview, "islandNotificationScroll");
                const lastPreviewAction = findChild(preview, "islandNotificationAction3");
                lastPreviewAction.forceActiveFocus(Qt.TabFocusReason);
                wait(100);
                const lastY = lastPreviewAction.mapToItem(previewScroll, 0, 0).y;
                check(previewScroll.contentItem.contentY > 0 && lastY >= -1 && lastY + lastPreviewAction.height <= previewScroll.height + 1, "Keyboard focus reveals a sender action after a long message");
                const previewDismiss = findChild(preview, "islandNotificationDismiss");
                const dismissY = previewDismiss.mapToItem(preview, 0, 0).y;
                check(dismissY >= 0 && dismissY + previewDismiss.height <= preview.height, "Dismiss stays in the fixed preview header");
                previewDismiss.clicked();
                check(preview.dismissals === 1, "Compact preview dismiss control responds");
                preview.destroy();
                const homeContent = findChild(dashboard, "islandHomeSummary").parent;
                const fourthAction = findChild(homeContent, "islandNotificationAction3");
                check(fourthAction !== null && fourthAction.text === "Fourth action", "All sender actions are available on Home");
                fourthAction.clicked();
                check(S.Notifications.invokedId === 1 && S.Notifications.invokedIndex === 3, "Fourth action preserves native action index");
                dashboard.anchors.fill = null; dashboard.width = 280; dashboard.height = 488;
                wait(100);
                for (let i = 0; i < 4; i++) {
                    const action = findChild(homeContent, "islandNotificationAction" + i);
                    check(action.x >= 0 && action.x + action.width <= action.parent.width + 1, "Wrapped notification action fits narrow card");
                }
                findChild(homeContent, "islandNotificationDismiss").clicked();
                check(S.Notifications.count === 0, "Home dismiss removes notification from island");
                S.Notifications.history = [{id: 11, appName: "Fixture", summary: "Inbox dismissal", body: "Body", time: new Date(), unread: true, actions: []}];
                dashboard.width = 608;
                findChild(dashboard, "islandTabInbox").clicked();
                check(dashboard.section === "inbox", "Expected dashboard.section");
                wait(350);
                check(S.Notifications.unread === 0, "Expected S.Notifications.unread");
                const inboxList = findChild(dashboard, "islandInboxList");
                const inboxDismiss = findChild(inboxList, "islandNotificationDismiss");
                check(inboxDismiss !== null, "Inbox provides a dismiss button");
                inboxDismiss.clicked();
                check(S.Notifications.count === 0, "Inbox dismiss removes notification from island");
                check(!findChild(dashboard, "islandInboxClear").enabled && !findChild(dashboard, "islandInboxRead").enabled, "Empty Inbox disables bulk controls");
                const dndButton = findChild(dashboard, "islandInboxDnd");
                dndButton.clicked();
                check(S.Notifications.dnd, "Inbox enables do not disturb");
                dndButton.clicked();
                check(!S.Notifications.dnd, "Inbox disables do not disturb");
                S.Notifications.history = [
                    {id: 12, appName: "Fixture", summary: "Read me", body: "", time: new Date(), unread: true, actions: []},
                    {id: 13, appName: "Other", summary: "Read me too", body: "", time: new Date(), unread: true, actions: []}
                ];
                check(findChild(dashboard, "islandInboxRead").enabled, "Unread entries enable mark all read");
                findChild(dashboard, "islandInboxRead").clicked();
                check(S.Notifications.unread === 0 && S.Notifications.count === 2, "Mark all read preserves history");
                findChild(dashboard, "islandInboxClear").clicked();
                check(S.Notifications.count === 0, "Clear all removes all island notifications");
                dashboard.active = true;
                S.Notifications.history = [{id: 2, appName: "Other app", summary: "New message", body: "Keep the selected page", time: new Date(), unread: true, actions: []}];
                dashboard.section = "controls";
                wait(350);
                check(S.Notifications.unread === 1, "Expected S.Notifications.unread");
                check(findChild(dashboard, "islandDashboardBrightness").enabled, "brightness enabled");
                check(dashboard.section === "controls", "Expected dashboard.section");
                const wifiControl = findChild(dashboard, "islandControlWifi");
                const bluetoothControl = findChild(dashboard, "islandControlBluetooth");
                const nightControl = findChild(dashboard, "islandControlNight");
                const dndControl = findChild(dashboard, "islandControlDnd");
                check(wifiControl && bluetoothControl && nightControl && dndControl, "Original connectivity controls exist");
                mouseClick(wifiControl, wifiControl.width / 2, wifiControl.height / 2);
                check(!S.Network.wifiEnabled, "Wi-Fi click changes service state");
                mouseClick(bluetoothControl, bluetoothControl.width / 2, bluetoothControl.height / 2);
                check(!S.Bluetooth.enabled, "Bluetooth click changes service state");
                mouseClick(nightControl, nightControl.width / 2, nightControl.height / 2);
                check(S.NightLight.active, "Night light click changes service state");
                dndControl.forceActiveFocus(Qt.TabFocusReason); keyClick(Qt.Key_Space);
                check(S.Notifications.dnd, "Keyboard activates DND");
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
                const controlsScroll = findChild(dashboard, "islandControlsScroll");
                const level = findChild(dashboard, "islandDashboardBrightness");
                controlsScroll.contentItem.contentY = Math.max(0, level.mapToItem(controlsScroll.contentItem, 0, 0).y - 20);
                wait(100);
                const volume = findChild(dashboard, "islandDashboardVolume");
                check(level.orientation === Qt.Vertical && volume.orientation === Qt.Vertical, "Brightness and volume use vertical sliders");
                check(Math.abs(level.value - S.Brightness.percent / 100) < .02, "Brightness reflects the service");
                check(Math.abs(volume.value - S.Audio.volume) < .02, "Volume reflects the service");
                mouseClick(level, level.width / 2, level.height * .6); wait(30);
                const lowerBrightness = S.Brightness.percent;
                mouseClick(level, level.width / 2, level.height * .2); wait(30);
                check(S.Brightness.percent > lowerBrightness + 10, "Brightness responds to vertical mouse clicks");
                mouseClick(volume, volume.width / 2, volume.height * .35); wait(30);
                const lowerVolume = S.Audio.volume;
                mouseClick(volume, volume.width / 2, volume.height * .1); wait(30);
                check(S.Audio.volume > lowerVolume + .1, "Volume responds to vertical mouse clicks outside mute");
                check(!S.Audio.muted, "Slider clicks do not toggle mute");
                level.value = .65; level.moved();
                check(Math.abs(S.Brightness.percent - 65) < .1, "Brightness writes reach the service");
                volume.value = .7; volume.moved();
                check(Math.abs(S.Audio.volume - .7) < .01, "Volume writes reach the service");
                const mute = findChild(dashboard, "islandVolumeMute");
                check(mute !== null && mute.width >= 40 && mute.height >= 40 && mute.visible, "Mute is a visible, usable target");
                controlsScroll.contentItem.contentY = Math.max(0, mute.mapToItem(controlsScroll.contentItem, 0, 0).y - 20);
                wait(100);
                mouseClick(mute, mute.width / 2, mute.height / 2);
                check(S.Audio.muted, "Mute click reaches the audio service " + JSON.stringify({x:mute.mapToItem(dashboard, 0, 0).x, y:mute.mapToItem(dashboard, 0, 0).y, enabled:mute.enabled, visible:mute.visible, scroll:controlsScroll.contentItem.contentY}));
                mouseClick(mute, mute.width / 2, mute.height / 2);
                check(!S.Audio.muted, "Mute click toggles back");
                check(findChild(dashboard, "islandDashboardRecord") === null && findChild(dashboard, "islandControlMore") === null && findChild(dashboard, "islandControlDetail0") === null, "Extra bottom tools are removed from the island");
                const finalControl = findChild(dashboard, "islandPowerProfile-performance");
                finalControl.forceActiveFocus(Qt.OtherFocusReason);
                wait(100);
                const scrollViewport = findChild(dashboard, "islandControlsScroll");
                const finalY = finalControl.mapToItem(scrollViewport.contentItem, 0, 0).y;
                check(finalY >= -1 && finalY + finalControl.height <= scrollViewport.height + 1, "Final power-profile control remains reachable");
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
    'SystemStats': '''property bool ready: true
property bool cpuAvailable: true
property bool memoryAvailable: true
property bool storageAvailable: true
property real cpuPercent: 27
property real memoryUsed: 6442450944
property real memoryTotal: 17179869184
property real storageUsed: 137438953472
property real storageTotal: 549755813888
property real memoryPercent: 37.5
property real storagePercent: 25
property string error: ""
function createConsumer() { return 1; }
function setDemand(id, value) {}
function releaseConsumer(id) {}
''',
    'Notifications': '''property var history: [{id: 1, appName: "Fixture", summary: "A notification", body: "A body", time: new Date(), unread: true, actions: ["Reply", "Open", "A long third action", "Fourth action"]}]
readonly property int count: history.length
readonly property int unread: history.filter(entry => entry.unread).length
property bool dnd: false
function toggleDnd() { dnd = !dnd; }
function markEntriesRead(ids) { history = history.map(entry => Object.assign({}, entry, {unread: ids.indexOf(entry.id) >= 0 ? false : entry.unread})); }
function dismissPopup(id) { history = history.map(entry => entry.id === id ? Object.assign({}, entry, {actions: []}) : entry); }
function dismiss(id) { history = history.filter(entry => entry.id !== id); }
function markRead() { history = history.map(entry => Object.assign({}, entry, {unread: false})); }
function clear() { history = []; }
property int invokedId: -1
property int invokedIndex: -1
function invoke(id, index) { invokedId = id; invokedIndex = index; }
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
        shutil.copytree(repo / 'shell/integrations', work / 'integrations')
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
        print('PASS: observed CPU/RAM/storage; unavailable truth; compact power controls; no bottom extras; tabs; visible-only unread handling; no incoming tab switching; Home/Inbox dismissal; all action routing; clear/read/DND; inactive Inbox; narrow layout')


if __name__ == '__main__':
    main()
