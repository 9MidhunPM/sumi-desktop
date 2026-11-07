#!/usr/bin/env python3
"""Exercise real island content/state with only native focus/window wrappers replaced."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HARNESS = r'''import QtQuick
import QtTest
import Quickshell
import "config"
import "services" as S
ShellRoot {
    QtObject { id: screenInfo; property string name: "fixture"; property int width: 1920; property int height: 1080 }
    QtObject {
        id: fakeApp
        property var activeScreen: screenInfo
        property var notificationScreen: screenInfo
        property var thursdayBackend: null
        property bool thursdayOutputActive: false
        property string thursdayOutputScreen: "fixture"
        property bool barVisible: true
        property string panel: ""
        property bool nativeDialogOpen: false
        property bool focusRunning: false
        property double focusDeadline: 0
        property double focusRemaining: 1500000
        property string lastPanel: ""
        function open(name, screen) { lastPanel = name; panel = name; return true; }
        function close() { panel = ""; }
        function resolveScreen(screen) { return screen || screenInfo; }
        function focusStart() { focusRunning = true; focusDeadline = Date.now() + focusRemaining; }
        function focusPause() { focusRemaining = Math.max(0, focusDeadline - Date.now()); focusRunning = false; }
        function focusReset(minutes) { focusRunning = false; focusRemaining = minutes * 60000; }
    }
    QtObject {
        id: player
        property string dbusName: "org.mpris.MediaPlayer2.fixture"
        property string identity: "Fixture"
        property bool isPlaying: false
        property string trackTitle: "A long track title that should fit without covering playback controls"
        property string trackArtist: "Your soundtrack"
        property string trackArtUrl: ""
        property bool canGoPrevious: true
        property bool canGoNext: true
        property bool canTogglePlaying: true
        property bool canSeek: true
        property bool lengthSupported: true
        property bool positionSupported: true
        property real position: 40
        property real length: 200
        property int toggles: 0
        property int previousCalls: 0
        property int nextCalls: 0
        function togglePlaying() { toggles++; isPlaying = !isPlaying; }
        function previous() { previousCalls++; }
        function next() { nextCalls++; }
    }
    QtObject {
        id: browser
        property string dbusName: "org.mpris.MediaPlayer2.brave"
        property string identity: "Brave"
        property string desktopEntry: "brave-browser"
        property bool positionSupported: false
        property bool lengthSupported: false
        property string trackTitle: "Brave"
        property string trackArtist: ""
        property string trackArtUrl: ""
        property bool isPlaying: false
    }
    QtObject {
        id: assistant
        property bool voiceActive: false
        property bool sendPending: false
        property bool busy: false
        property bool taskActive: false
        property bool speaking: true
        property var confirmations: []
        property string statusText: "Speaking"
        property string transcript: "A voice question"
        property string latestAnswer: "The actual response appears here as plain text."
        property int playbackPosition: 200
        property var audioEnvelope: ({interval_ms: 20, levels: Array(30).fill(.25)})
    }
    DynamicIsland { id: island; app: fakeApp; modelData: screenInfo; centerRoom: 500 }
    TestCase {
        name: "SumiDynamicIsland"
        when: true
        function check(value, label) {
            if (!value) { console.error("SUMI_ISLAND_FAILED", label); Qt.exit(1); throw new Error(label); }
        }
        function ready(condition, label) {
            let elapsed = 0;
            while (!condition() && elapsed < 3000) { wait(10); elapsed += 10; }
            check(condition(), label);
        }
        function child(name) { return findChild(island.contentItem, name); }
        property int centerChecks: 0
        function center() {
            centerChecks++;
            const clock = child("barClockTime");
            check(clock !== null, "Numeric clock exists");
            const point = clock.mapToItem(island.contentItem, 0, 0);
            check(Math.abs(point.x + clock.width / 2 - island.width / 2) < .6, "Clock remains exactly centered " + JSON.stringify({check:centerChecks, frameWidth:island.width, bodyWidth:island.bodyWidth, headerWidth:island.visual.headerWidth, pointX:point.x, clockWidth:clock.width, clockX:clock.x, parentWidth:clock.parent.width, parentX:clock.parent.x, parentParentX:clock.parent.parent.x, time:clock.text, pinned:island.pinned, expanded:island.expanded}));
            check(point.y >= 0 && point.y + clock.height <= island.visual.headerHeight, "Clock remains in its header");
        }
        function assertClosed(label) {
            check(!island.pinned && !island.expanded && !island.smokeGrab.active, label + " dismisses state and grab");
            check(island.inputHeight <= (island.notch ? 40.1 : 36.1), label + " restores compact input region");
        }
        function test_island() {
            ready(() => !Settings.loading, "Settings initialized");
            Settings.reducedMotion = true;
            Settings.islandNotch = false;
            island.idle = false;
            island.monitor = {activeWorkspace: {hasFullscreen: false}};
            S.Media.players = [];
            wait(30);
            check(island.visible && !island.expanded, "Idle island maps compact");
            for (const available of [132, 240, 500]) {
                island.centerRoom = available; wait(5); center();
                check(island.bodyWidth <= available + .5, "Compact width respects side islands " + JSON.stringify({available:available,width:island.bodyWidth,min:island.minimumClockWidth,activity:island.activity,expanded:island.expanded,pinned:island.pinned,event:S.IslandEvents.eventKind}));
            }
            island.centerRoom = 500;
            const pixels = grabImage(island.contentItem);
            const bodyX = Math.floor(island.inputX);
            const x = Math.floor(island.width / 2);
            check(pixels.alpha(x, 2) === 255 && pixels.red(x, 2) === 0 && pixels.green(x, 2) === 0 && pixels.blue(x, 2) === 0, "Body is opaque pitch black with no glass sheen");
            check(pixels.alpha(bodyX, 0) === 0, "Floating body has rounded upper corners");
            island.enterHover(); wait(100);
            check(!island.expanded && !island.smokeGrab.active, "Intentional hover delay does not grab input");
            wait(90); check(island.expanded && !island.pinned && !island.smokeGrab.active, "Hover peeks without taking keyboard ownership"); center();
            island.leaveHover(); wait(100); check(island.expanded, "Pointer exit has grace");
            wait(200); assertClosed("Pointer exit");
            island.enterHover(); wait(180); island.pin(); wait(20);
            check(island.pinned && island.smokeGrab.active, "Explicit pin owns focus grab");
            island.leaveHover(); wait(300); check(island.pinned && island.expanded, "Pinned island survives pointer leave");
            island.enterHover(); keyClick(Qt.Key_Escape); wait(20); assertClosed("Escape");
            island.enterHover(); wait(180); check(!island.expanded, "Dismiss suppresses reopening until pointer leaves");
            island.leaveHover(); island.enterHover(); wait(180); check(island.expanded, "Fresh entry resumes hover");
            island.pin(); wait(10); island.smokeGrab.cleared(); wait(20); assertClosed("Outside click");
            for (const mode of [false, true]) {
                Settings.islandNotch = mode; island.dismiss(); wait(10); center();
                check(island.notch === mode && Math.abs(island.bodyHeight - (mode ? 40 : 36)) < .5, "Notch changes connector height");
                const frame = grabImage(island.contentItem);
                check((frame.alpha(Math.floor(island.inputX), 0) > 250) === mode, "Only notch has flat upper shoulders");
                if (mode) {
                    const shoulder = island.visual.rightFillet;
                    check(frame.alpha(Math.floor(shoulder.x + 1), 1) > 230, "Notch shoulder attaches to the top bezel");
                    check(frame.alpha(Math.floor(shoulder.x + shoulder.width - 2), shoulder.height - 2) < 20, "Concave notch shoulder curves away into transparency");
                }
                frame.save("/tmp/sumi-island-" + (mode ? "notch" : "pill") + ".png");
            }
            Settings.islandNotch = false;
            S.IslandEvents.availableScreens = ["fixture", "different-output"];
            S.Media.players = [browser]; wait(20);
            island.leaveHover(); island.enterHover(); wait(180);
            check(!S.IslandMedia.available && child("islandWeekStrip").visible, "Idle browser shows date glance on hover");
            browser.isPlaying = true; browser.trackTitle = "A meaningful video"; wait(20);
            check(S.IslandMedia.player === browser && !child("islandWeekStrip").visible, "Meaningful playing browser media is represented");
            browser.isPlaying = false; wait(20);
            check(!S.IslandMedia.available, "Stale paused browser media is omitted");
            player.dbusName = "org.mpris.MediaPlayer2.spotify.fixture";
            S.Media.players = [browser, player]; wait(20);
            check(S.IslandMedia.player === player && child("islandPlay").enabled, "Paused Spotify remains playable");
            island.dismiss();
            S.Media.players = [player]; player.isPlaying = true; wait(20);
            check(island.activity === "media" && island.spectrumDemand, "Visible compact media owns spectrum demand");
            island.centerRoom = 132; island.pin(); wait(30);
            check(island.bodyWidth > 420 && !island.visual.hasFlanks && !island.spectrumDemand, "Dashboard grows below narrow header without hidden spectrum work");
            check(child("islandTabControls") && child("islandTabControls").activeFocus, "Explicit pin focuses dashboard navigation");
            check(!child("islandDetails").visible, "Full dashboard replaces the hover glance");
            island.dismiss(); island.centerRoom = 500; wait(20);

            S.IslandEvents.show("volume", "42%", .42, 80, "different-output"); wait(5);
            check(island.activity === "media", "Events only present on their selected output");
            S.IslandEvents.show("volume", "42%", .42, 80, "fixture"); wait(5);
            check(island.activity === "event", "Volume transient overrides persistent activity"); center();
            wait(100); check(island.activity === "media", "Transient expiration restores media");
            island.pin("media"); wait(30);
            check(island.section === "media" && island.progressDemand && !island.spectrumDemand, "Only visible Media page requests position updates");
            check(island.bodyHeight < island.height && island.bodyHeight >= 280, "Media island hugs its content instead of leaving a full-height empty panel");
            grabImage(island.contentItem).save("/tmp/sumi-island-expanded.png");
            const play = child("islandDashboardPlay");
            check(play && play.enabled, "Dashboard playback control is available");
            const previous = player.toggles; play.clicked(); wait(5);
            check(player.toggles === previous + 1, "Dashboard playback invokes the selected player");
            player.isPlaying = true;
            child("islandTabControls").clicked(); wait(20);
            check(island.section === "controls" && !island.progressDemand, "Switching tabs releases hidden media progress work");
            S.IslandEvents.clear(); wait(30);
            function pinnedGeometry() {
                const frame = child("islandDashboardFrame"), dashboard = child("islandDashboardLoader"), header = child("islandHeader"), surface = child("islandBody");
                const dashboardPosition = dashboard.mapToItem(island.contentItem,0,0);
                return [island.bodyWidth,island.bodyHeight,header.x,header.y,surface.x,surface.y,surface.width,surface.height,frame.x,frame.y,frame.width,frame.height,dashboardPosition.x,dashboardPosition.y,dashboard.width,dashboard.height];
            }
            const settledGeometry = pinnedGeometry();
            function stablePinned(label) {
                const current = pinnedGeometry();
                check(island.pinned && island.section === "controls", label + " preserves pinned page");
                for (let index=0;index<current.length;index++)
                    check(Math.abs(current[index]-settledGeometry[index]) < .5, label + " cannot move or resize pinned geometry " + index + ": " + JSON.stringify(current) + " vs " + JSON.stringify(settledGeometry));
            }
            for (const event of [["volume","70%",.7],["brightness","18%",.18],["microphone","Mic muted",0],["network","Wi-Fi on",1],["critical-battery","5% battery",.05]]) {
                S.IslandEvents.show(event[0],event[1],event[2],80,"fixture"); wait(10);
                check(island.visual.eventLabel === event[1], "Feedback remains available in fixed header");
                stablePinned(event[0] + " onset");
                wait(90); stablePinned(event[0] + " expiry");
                S.IslandEvents.clear();
            }
            const notification = {id:9901,appName:"Fixture",summary:"A notification while adjusting controls",body:"Keep the panel still",time:new Date(),unread:true,popup:true,critical:false,actions:[]};
            S.Notifications.live = ({9901:{}}); S.Notifications.history = [notification];
            S.IslandEvents.show("notification",notification.summary,0,80,"fixture",{notificationId:9901}); wait(10);
            check(island.visual.notification && island.visual.notification.id === 9901,"Live notification remains represented");
            stablePinned("notification onset");
            wait(90); stablePinned("notification expiry");
            S.IslandEvents.clear(); S.Notifications.live = ({}); S.Notifications.history = [];
            grabImage(island.contentItem).save("/tmp/sumi-island-controls.png");
            child("islandTabHome").clicked(); wait(220);
            check(child("islandUsage-cpu") !== null, "Home exposes actual system usage in place of large task tiles");
            check(child("islandDashboardFocus") === null, "Home no longer prioritizes focus controls");
            island.dismiss();
            for (const trigger of ["panel", "native", "hidden", "fullscreen", "idle", "output"]) {
                island.leaveHover(); island.pin(); wait(20);
                if (trigger === "panel") fakeApp.panel = "settings";
                if (trigger === "native") fakeApp.nativeDialogOpen = true;
                if (trigger === "hidden") fakeApp.barVisible = false;
                if (trigger === "fullscreen") island.monitor = {activeWorkspace: {hasFullscreen: true}};
                if (trigger === "idle") island.idle = true;
                if (trigger === "output") island.modelData = null;
                wait(20); check(!island.pinned && !island.smokeGrab.active && !island.spectrumDemand, trigger + " releases interactive work");
                fakeApp.panel = ""; fakeApp.nativeDialogOpen = false; fakeApp.barVisible = true;
                island.modelData = screenInfo; island.monitor = {activeWorkspace: {hasFullscreen: false}}; island.idle = false; wait(30);
            }
            island.monitor = {activeWorkspace: {hasFullscreen: true}}; wait(20);
            S.IslandEvents.show("volume", "Quiet fullscreen", .4, 1000, "fixture"); wait(10);
            check(!island.visible, "Routine fullscreen feedback stays hidden");
            S.IslandEvents.show("critical-battery", "5% battery", .05, 1000, "fixture"); wait(20);
            check(island.visible && island.expanded && !island.smokeGrab.active, "Critical fullscreen preview never takes keyboard focus");
            S.IslandEvents.dismissCurrent(); wait(20);
            island.pin("inbox"); wait(30);
            check(island.visible && island.pinned && island.section === "inbox", "Explicit dashboard request works during fullscreen");
            island.dismiss(); island.monitor = {activeWorkspace: {hasFullscreen: false}}; wait(20);
            screenInfo.width = 344; wait(30); island.pin("controls"); wait(30);
            check(island.bodyWidth <= 320 && island.bodyHeight <= screenInfo.height - 64, "Dashboard adapts to narrow outputs");
            center(); grabImage(island.contentItem).save("/tmp/sumi-island-narrow.png");
            island.dismiss(); screenInfo.width = 1920; wait(30);
            fakeApp.thursdayBackend = assistant;
            fakeApp.thursdayOutputActive = true;
            assistant.speaking = true; wait(30);
            check(island.assistantOutputHere && island.expanded && !island.pinned && !island.smokeGrab.active, "Thursday output expands without keyboard ownership");
            const output = child("islandAssistantOutput");
            check(output.visible && output.text === assistant.latestAnswer, "Automatic speech shows response text rather than transcript or the full dashboard");
            check(child("islandTabThursday") === null, "Automatic reply never instantiates the full assistant dashboard");
            check(island.speechSamples.some(value => value > 0) && child("islandWave19").height > 2, "Thursday uses measured speech in the same header bars as music");
            center();
            assistant.speaking = false; wait(20);
            check(island.assistantOutputHere && island.speechSamples.every(value => value === 0), "Reading pause retains text while silent output clears the waveform");
            S.IslandEvents.show("critical-battery", "5% battery", .05, 1000, "fixture"); wait(20);
            check(!island.assistantOutputHere && island.expanded, "Critical alerts can preempt the text-only assistant output");
            S.IslandEvents.clear(); fakeApp.thursdayOutputActive = false; fakeApp.thursdayBackend = null; wait(20);
            check(!island.expanded && !island.smokeGrab.active, "Finished assistant output returns to the compact island");
            Settings.reducedMotion = false;
            island.leaveHover(); wait(10); island.pin();
            check(island.pinned, "Animation pin accepted after eligibility restoration");
            let intermediate = false; const heights = [];
            for (let frame = 0; frame < 22; frame++) { wait(16); center(); heights.push(island.bodyHeight); if (island.bodyHeight > 42 && island.bodyHeight < island.height - 1) intermediate = true; }
            check(intermediate, "Expansion includes real intermediate shape frames " + JSON.stringify(heights) + " reduced=" + Theme.effectiveReducedMotion);
            island.dismiss(); wait(25); island.leaveHover(); island.pin(); wait(400); center();
            Settings.reducedMotion = true; island.dismiss(); wait(5); assertClosed("Reduced motion");
            Settings.islandNotch = false;
            S.Media.players = [];
            console.info("SUMI_ISLAND_OK"); Qt.quit();
        }
    }
}
'''

def adapt(source: str) -> str:
    source = source.replace('PanelWindow {', 'Window {', 1)
    source = re.sub(r'^    (screen:|anchors \{|margins[. {]|exclusionMode:|exclusiveZone:|WlrLayershell\.).*\n', '', source, flags=re.M)
    source = re.sub(r'^    implicit(Width|Height):', lambda m: '    ' + m[1].lower() + ':', source, flags=re.M)
    source = re.sub(r'    mask: Region \{.*?^    \}\n', '', source, flags=re.M | re.S)
    source = source.replace('HyprlandFocusGrab {', 'QtObject {', 1)
    source = source.replace('        id: focusGrab', '        id: focusGrab\n        property bool active: false\n        signal cleared()', 1)
    source = source.replace('        windows: [root]', '        property var windows: [root]', 1)
    source = source.replace('    color: "transparent"', '    readonly property var smokeGrab: focusGrab\n    color: "transparent"', 1)
    return source

def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sumi-island-') as temporary:
        work = Path(temporary); config = work / 'shell'
        shutil.copytree(repo / 'shell', config)
        path = config / 'DynamicIsland.qml'; path.write_text(adapt(path.read_text()))
        visual = config / 'components/IslandContent.qml'
        visual.write_text(visual.read_text().replace('HoverHandler {', 'HoverHandler { enabled: false;'))
        media = config / 'services/Media.qml'
        media.write_text(media.read_text().replace('readonly property var players: Mp.Mpris.players.values', 'property var players: []').replace(' && !Desktop.preview', ''))
        island_media = config / 'services/IslandMedia.qml'
        island_media.write_text(island_media.read_text().replace(' && !Desktop.preview', ''))
        (config / 'shell.qml').write_text(HARNESS)
        runtime = work / 'runtime'; runtime.mkdir(mode=0o700)
        environment = dict(os.environ, SUMI_PREVIEW='1', SUMI_STATE_DIR=str(work / 'state'), QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(['qs', '-p', str(config)], env=environment, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        if result.returncode or 'SUMI_ISLAND_OK' not in output or any(token in output for token in ['TypeError:', 'ReferenceError:', 'Failed to load configuration', 'Unable to assign [undefined]', 'FAIL!', 'Binding loop']):
            raise SystemExit(output)
        print('PASS: outlined black pill/notch; centered clock; hover/pin/focus lifecycle; dashboard tabs/media; pinned feedback geometry stability; fullscreen critical and explicit access; narrow layout; demand gates; reduced motion')
        print('Native input grab, outside-click delivery and monitor geometry require compositor validation')

if __name__ == '__main__': main()
