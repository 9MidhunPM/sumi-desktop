#!/usr/bin/env python3
"""Exercise the real island event arbiter against isolated service signals."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "services" as S
ShellRoot {
    TestCase {
        name: "IslandEvents"
        when: true
        function check(value, message) {
            if (!value) { console.error("ISLAND_EVENTS_FAILED", message); Qt.exit(1); throw new Error(message); }
        }
        function test_events() {
            S.IslandEvents.availableScreens = ["eDP-1", "HDMI-A-1"];
            S.IslandEvents.focusedScreenName = "eDP-1";
            S.Audio.volume = .6; S.Audio.muted = true;
            S.Battery.percent = 4; S.Battery.available = true;
            S.Audio.ready = true;
            wait(550);
            check(S.IslandEvents.criticalAttention, "Critical battery on startup retains attention without a preview");
            check(S.IslandEvents.audioArmed && S.IslandEvents.batteryArmed && !S.IslandEvents.active, "Service startup is a silent baseline even at low battery");
            S.Audio.muted = false;
            check(S.IslandEvents.eventKind === "volume" && S.IslandEvents.eventLabel === "60%" && S.IslandEvents.eventValue === .6, "Output change has useful feedback");
            check(S.IslandEvents.eventScreenName === "eDP-1", "Feedback routes to the focused output");
            const firstExpiry = S.IslandEvents.expiresAt;
            wait(20); S.Audio.volume = .7;
            check(S.IslandEvents.eventLabel === "70%" && S.IslandEvents.expiresAt > firstExpiry, "Repeated volume changes coalesce and extend the timeout");
            S.IslandEvents.focusedScreenName = "HDMI-A-1";
            S.Audio.sourceMuted = true;
            check(S.IslandEvents.eventKind === "microphone" && S.IslandEvents.eventLabel === "Mic muted" && S.IslandEvents.eventScreenName === "HDMI-A-1", "Microphone feedback and output routing update together");
            S.IslandEvents.displayEnabled = false;
            S.Audio.volume = .2;
            S.Battery.percent = 40;
            check(!S.IslandEvents.active, "Hidden island drops events");
            S.IslandEvents.displayEnabled = true;
            check(!S.IslandEvents.active, "Showing the island does not replay old feedback");
            S.Audio.volume = .3;
            check(S.IslandEvents.eventLabel === "30%", "Hidden audio changes still updated the baseline");

            S.IslandEvents.clear(); S.Battery.percent = 20;
            check(S.IslandEvents.eventKind === "low-battery" && S.IslandEvents.eventLabel === "20% battery", "First battery threshold alerts");
            S.IslandEvents.clear(); S.Battery.percent = 19;
            check(!S.IslandEvents.active, "Further percentage updates do not repeat the threshold alert");
            S.Battery.percent = 10;
            check(S.IslandEvents.eventKind === "low-battery" && S.IslandEvents.eventValue === .1, "Critical threshold alerts separately");
            S.IslandEvents.clear(); S.Battery.percent = 9;
            check(!S.IslandEvents.active, "Critical battery alert is not repeated per percentage");
            S.Battery.onBattery = false; S.Battery.charging = true;
            check(S.IslandEvents.eventKind === "power" && S.IslandEvents.eventLabel === "Charging", "Plugging in becomes one coalesced charging event");
            S.IslandEvents.clear(); S.Battery.charging = false;
            check(!S.IslandEvents.active, "Fully charged is not mistaken for unplugging");
            S.Battery.percent = 80; S.Battery.onBattery = true;
            check(S.IslandEvents.eventLabel === "On battery", "Unplugging has explicit feedback");
            S.IslandEvents.clear(); S.Battery.percent = 5;
            check(S.IslandEvents.eventKind === "critical-battery" && S.IslandEvents.eventLabel === "5% battery", "A direct jump through both thresholds shows the critical level once");
            check(S.IslandEvents.eventCritical && S.IslandEvents.expiresAt - Date.now() > 7900, "Five percent battery is critical with a bounded eight-second preview");
            S.Audio.volume = .8;
            check(S.IslandEvents.eventKind === "critical-battery", "Audio cannot erase critical battery");
            S.IslandEvents.clear();
            S.IslandEvents.publishFocusComplete("eDP-1");
            check(S.IslandEvents.eventKind === "focus-complete" && S.IslandEvents.eventScreenName === "eDP-1", "Focus completion can target the initiating screen");
            check(S.IslandEvents.expiresAt - Date.now() > 4900, "Completion gets a five-second lifetime");
            S.IslandEvents.clear();
            S.IslandEvents.show("volume", "Newest", .2, 80);
            wait(30); S.IslandEvents.show("volume", "Latest", .3, 80);
            wait(55);
            check(S.IslandEvents.active && S.IslandEvents.eventLabel === "Latest", "Replacing an event cancels the previous expiration");
            wait(50);
            check(!S.IslandEvents.active && S.IslandEvents.expiresAt === 0 && S.IslandEvents.eventScreenName === "", "Event expiration clears the full transient state");
            S.Audio.ready = false; S.Audio.volume = .9; S.Audio.ready = true;
            wait(550);
            check(!S.IslandEvents.active, "Reconnecting audio silently re-arms its baseline");
            S.IslandEvents.focusedScreenName = "eDP-1";
            S.Battery.percent = 30; S.IslandEvents.clear();
            S.Battery.percent = 20; S.IslandEvents.clear();
            S.Battery.percent = 21; S.Battery.percent = 20;
            check(!S.IslandEvents.active, "Battery jitter does not rearm thresholds");
            S.Battery.percent = 23; S.Battery.percent = 20;
            check(S.IslandEvents.eventKind === "low-battery", "Three point battery recovery rearms warning");
            S.IslandEvents.clear();
            S.Brightness.available = true; S.Brightness.percent = 40; S.Brightness.ready = true;
            check(!S.IslandEvents.active, "First brightness read is silent");
            S.Brightness.percent = 45;
            check(!S.IslandEvents.active, "Optimistic slider targets do not claim hardware success");
            S.Brightness.changed(45);
            check(S.IslandEvents.eventKind === "brightness" && S.IslandEvents.eventValue === .45 && S.IslandEvents.eventSection === "controls", "Brightness publishes control feedback");

            S.IslandEvents.clear();
            S.IslandEvents.fullscreenScreens = ["eDP-1"];
            S.Audio.volume = .4; S.Brightness.percent = 50; S.Brightness.changed(50);
            S.Notifications.add(1, false);
            check(!S.IslandEvents.active && S.IslandEvents.pendingCount === 0, "Routine fullscreen feedback is dropped");
            S.Notifications.add(2, true);
            check(S.IslandEvents.eventCritical && S.IslandEvents.notification.id === 2 && S.IslandEvents.criticalAttention, "Critical app notification crosses fullscreen");
            check(S.IslandEvents.expiresAt - Date.now() <= 8000, "Critical app preview has a maximum eight-second lifetime");
            const criticalDeadline = S.IslandEvents.expiresAt;
            S.Notifications.update(2, true, "Replacement");
            check(S.IslandEvents.notification.summary === "Replacement" && S.IslandEvents.eventLabel === "Replacement" && S.IslandEvents.expiresAt === criticalDeadline, "Replace-ID updates content without replaying preview");
            S.Notifications.update(2, false, "Downgraded");
            check(!S.IslandEvents.active, "Urgency downgrade immediately removes fullscreen presentation");
            S.IslandEvents.fullscreenScreens = [];
            check(!S.IslandEvents.active, "Leaving fullscreen never replays discarded previews");

            S.Notifications.reset();
            S.Notifications.add(10, false);
            check(S.IslandEvents.notification.id === 10 && S.IslandEvents.eventSection === "inbox", "Notification uses Inbox section");
            S.Notifications.add(11, false); S.Notifications.add(12, false); S.Notifications.add(13, false); S.Notifications.add(14, false);
            check(S.IslandEvents.pendingCount === 3, "Burst holds at most three pending notification identities");
            S.Notifications.add(15, true);
            check(S.IslandEvents.notification.id === 15 && S.IslandEvents.pendingCount === 3, "Critical app notification preempts ordinary notification and bounds its queue");
            S.IslandEvents.show("volume", "Do not replace", .5, 50);
            check(S.IslandEvents.notification.id === 15, "Routine feedback never overwrites critical app preview");
            S.Notifications.close(15);
            check(S.IslandEvents.notification.id === 10 && S.IslandEvents.pendingCount === 2, "Closed critical notification restores oldest still-live preview");
            S.Notifications.close(11);
            check(S.IslandEvents.pendingCount === 1, "Sender close removes queued notification identity");
            S.IslandEvents.dismissCurrent();
            check(!S.Notifications.history.find(item => item.id === 10).popup && S.IslandEvents.notification.id === 12, "Dismissing active popup advances the live queue");
            S.Notifications.dnd = true;
            check(!S.IslandEvents.active && S.IslandEvents.pendingCount === 0, "DND clears current and pending previews");
            S.Notifications.add(16, true);
            check(!S.IslandEvents.active && !S.IslandEvents.criticalAttention, "DND also suppresses critical app previews and attention");
            S.Notifications.dnd = false;
            check(!S.IslandEvents.active, "Leaving DND never replays a notification");

            S.Notifications.reset(); S.IslandEvents.clear();
            S.Notifications.add(30, true); S.Notifications.add(31, false);
            S.IslandEvents.show("notification", "Short pending", 0, 20, "eDP-1", {notificationId: 31, section: "inbox"});
            wait(40); S.IslandEvents.dismissCurrent();
            check(!S.IslandEvents.active && S.IslandEvents.pendingCount === 0 && !!S.Notifications.live[31], "Expired queued previews never replay or shorten the native lifetime");
            S.Notifications.reset();
            S.Notifications.add(32, false); S.Notifications.add(33, false);
            S.Notifications.update(33, true, "Urgent replacement");
            check(S.IslandEvents.notification.id === 33 && S.IslandEvents.eventCritical, "Queued urgency upgrade preempts an ordinary preview");
            S.Notifications.reset(); S.IslandEvents.clear();
            S.Notifications.add(20, true);
            S.IslandEvents.clear();
            S.IslandEvents.show("notification", "Bounded", 0, 50, "eDP-1", {notificationId: 20, critical: true, priority: 100, section: "inbox"});
            wait(80);
            check(!S.IslandEvents.active && S.IslandEvents.criticalAttention && !!S.Notifications.live[20], "Preview expiration retains critical attention and native lifetime");
            S.Notifications.close(20);
            check(!S.IslandEvents.criticalAttention, "Closing the native notification clears attention");
            S.IslandEvents.displayEnabled = false; S.Notifications.add(21, false);
            S.IslandEvents.displayEnabled = true;
            check(!S.IslandEvents.active, "Hidden notifications remain in Inbox without later replay");
            S.Notifications.reset();
            S.IslandEvents.show("brightness", "Monitor fallback", .3, 500, "missing-screen");
            check(S.IslandEvents.eventScreenName === "eDP-1", "Unavailable target falls back to focused output");
            const monitorDeadline = S.IslandEvents.expiresAt;
            S.IslandEvents.availableScreens = ["HDMI-A-1"];
            check(S.IslandEvents.eventScreenName === "HDMI-A-1" && S.IslandEvents.expiresAt === monitorDeadline, "Hotplug reroutes without restarting lifetime");
            S.IslandEvents.availableScreens = [];
            check(!S.IslandEvents.active, "No outputs drops presentation state");
            S.IslandEvents.availableScreens = ["eDP-1"]; check(!S.IslandEvents.active, "Reattached output does not replay stale feedback");
            wait(550); S.Network.connected = true; S.Network.name = "Home";
            check(S.IslandEvents.eventKind === "network", "Connection state creates feedback without requesting discovery");
            S.IslandEvents.clear(); S.Bluetooth.enabled = true;
            check(S.IslandEvents.eventKind === "bluetooth", "Bluetooth state creates feedback without requesting discovery");
            console.info("ISLAND_EVENTS_OK"); Qt.quit();
        }
    }
}
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sumi-island-events-') as temporary:
        work = Path(temporary)
        services = work / 'services'
        services.mkdir()
        shutil.copy2(repo / 'shell/services/IslandEvents.qml', services)
        (services / 'qmldir').write_text(''.join(f'singleton {name} {name}.qml\n' for name in ('IslandEvents', 'Audio', 'Battery', 'Brightness', 'Notifications', 'Network', 'Bluetooth')))
        prefix = 'pragma Singleton\nimport QtQuick\nimport Quickshell\nSingleton {\n'
        (services / 'Audio.qml').write_text(prefix + '''property bool ready: false
property bool hasOutput: true
property bool hasInput: true
property real volume: .5
property bool muted: false
property bool sourceMuted: false
}''')
        (services / 'Battery.qml').write_text(prefix + '''property bool available: false
property bool onBattery: true
property bool charging: false
property real percent: 50
}''')
        (services / 'Brightness.qml').write_text(prefix + "property bool ready: false\nproperty bool available: false\nproperty real percent: 0\nsignal changed(real value)\n}")
        (services / 'Network.qml').write_text(prefix + 'property string name: "Offline"\nproperty bool connected: false\n}')
        (services / 'Bluetooth.qml').write_text(prefix + 'property bool enabled: false\nproperty int connectedCount: 0\n}')
        (services / 'Notifications.qml').write_text(prefix + '''property var history: []
property var live: ({})
property bool dnd: false
signal received(var entry)
onDndChanged: if (dnd) history = history.map(item => Object.assign({}, item, {popup: false}))
function add(id, critical) {
    const item = {id: id, summary: "Notification " + id, appName: "Test", critical: critical, popup: !dnd};
    live = Object.assign({}, live, {[id]: true}); history = [item].concat(history); received(item);
}
function update(id, critical, text) { history = history.map(item => item.id === id ? Object.assign({}, item, {critical: critical, summary: text}) : item); }
function close(id) {
    const next = Object.assign({}, live); delete next[id]; live = next;
    history = history.map(item => item.id === id ? Object.assign({}, item, {popup: false}) : item);
}
function dismissPopup(id) { close(id); }
function reset() { history = []; live = ({}); dnd = false; }
}''')
        (work / 'shell.qml').write_text(HARNESS)
        runtime = work / 'runtime'
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(runtime), SUMI_PREVIEW='1')
        result = subprocess.run(['qs', '-p', str(work)], env=environment, text=True, capture_output=True, timeout=10)
        output = result.stdout + result.stderr
        if result.returncode or 'ISLAND_EVENTS_OK' not in output or any(message in output for message in ['TypeError:', 'ReferenceError:', 'Unable to assign [undefined]', 'Failed to load configuration', 'FAIL!']):
            raise SystemExit(output)
        print('PASS: startup/reconnect; priority/coalescing; bounded live notification queue; replace-ID/close/DND; fullscreen; critical attention; battery hysteresis; brightness/audio/connectivity; focus completion')


if __name__ == '__main__':
    main()
