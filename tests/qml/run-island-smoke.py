#!/usr/bin/env python3
"""Exercise real island content/state with only native focus/window wrappers replaced."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import struct
import zlib

HARNESS = r'''import QtQuick
import QtTest
import Quickshell
import "config"
import "services" as S
ShellRoot {
    S.IslandSession { id: session }
    QtObject { id: screenInfo; property string name: "fixture"; property int width: 1920; property int height: 1080 }
    QtObject {
        id: fakeApp
        property var islandSession: session
        property var codexStatus: null
        property string settingsSection: ""
        property int activationSerial: 0
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
        property bool canGoPrevious: false
        property bool canGoNext: false
        property bool canTogglePlaying: false
        property bool canSeek: false
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
        property string activity: "Opening Downloads"
        property real visualizerLevel: speaking ? .25 : 0
        property bool recording: false
        property string transcript: "A voice question"
        property string finalTranscript: "A voice question"
        property string partialTranscript: "A draft question"
        property string voiceState: "submitted"
        property string voiceError: ""
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
        property var clockMetrics: ({})
        function center() {
            centerChecks++;
            const clock = child("barClockTime");
            check(clock !== null, "Numeric clock exists");
            const point = clock.mapToItem(island.contentItem, 0, 0);
            const period = child("barClockPeriod"), pp = period.mapToItem(island.contentItem, 0, 0);
            check(clock.font.pixelSize === 26 && period.font.pixelSize === 10, "Clock and period maintain fixed font sizes");
            const key = String(island.notch), metric = [point.y, clock.width, clock.height, clock.baselineOffset, pp.x - point.x, pp.y, period.width, period.height, period.baselineOffset];
            if (clockMetrics[key]) for (let i=0; i<metric.length; i++) check(Math.abs(metric[i]-clockMetrics[key][i]) < .6, "Clock and period retain screen-space geometry and baseline " + key + " " + i + " " + JSON.stringify(metric) + " vs " + JSON.stringify(clockMetrics[key]));
            else clockMetrics[key] = metric;
            check(Math.abs(point.x + clock.width / 2 - island.width / 2) < .6, "Clock remains exactly centered " + JSON.stringify({check:centerChecks, frameWidth:island.width, bodyWidth:island.bodyWidth, headerWidth:island.visual.headerWidth, pointX:point.x, clockWidth:clock.width, clockX:clock.x, parentWidth:clock.parent.width, parentX:clock.parent.x, parentParentX:clock.parent.parent.x, time:clock.text, pinned:island.pinned, expanded:island.expanded}));
            check(point.y >= 0 && point.y + clock.height <= island.visual.headerHeight, "Clock remains in its header");
        }
        function assertClosed(label) {
            check(!island.pinned && !island.expanded && !island.smokeGrab.active, label + " dismisses state and grab");
            check(island.inputHeight <= (island.activity === "media" ? 50.1 : island.notch ? 46.1 : 42.1), label + " restores compact input region");
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
            island.enterHover(); wait(25);
            check(!island.expanded && !island.smokeGrab.active, "Intentional hover delay does not grab input");
            wait(140); check(island.expanded && !island.pinned && !island.smokeGrab.active, "Hover peeks without taking keyboard ownership"); center();
            island.leaveHover(); wait(25); check(island.expanded, "Pointer exit has grace");
            wait(350); assertClosed("Pointer exit");
            island.enterHover(); wait(180); island.pin(); ready(() => island.visual.dashboardReady, "Dashboard destination layout ready"); wait(20);
            check(island.pinned && island.smokeGrab.active, "Explicit pin owns focus grab");
            island.leaveHover(); wait(300); check(island.pinned && island.expanded, "Pinned island survives pointer leave");
            island.enterHover(); keyClick(Qt.Key_Escape); wait(20); assertClosed("Escape");
            island.enterHover(); wait(180); check(!island.expanded, "Dismiss suppresses reopening until pointer leaves");
            island.leaveHover(); island.enterHover(); wait(180); check(island.expanded, "Fresh entry resumes hover");
            island.pin(); wait(10); island.smokeGrab.cleared(); wait(20); assertClosed("Outside click");
            for (const route of ["media", "wifi", "appearance", "thursday"]) {
                island.pin(route); wait(180);
                check(island.pinned && island.section === route, "Detail page opens before Escape " + route);
                keyClick(Qt.Key_Escape); wait(30); assertClosed("Escape from " + route);
                island.visual.headerClicked(); wait(100);
                check(island.pinned && !island.previewPinned && island.section === "controls", "Header opens full controls after " + route);
                keyClick(Qt.Key_Escape); wait(30); assertClosed("Escape from main controls");
            }
            for (const mode of [false, true]) {
                Settings.islandNotch = mode; island.dismiss(); wait(10); center();
                check(island.notch === mode && Math.abs(island.bodyHeight - (mode ? 46 : 42)) < .5, "Notch changes connector height");
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
            S.Media.players = [player]; player.isPlaying = true; wait(400);
            check(island.activity === "media" && island.spectrumDemand, "Visible compact media owns spectrum demand");
            check(island.compactWidth <= 220 && !child("islandHeaderActivityLabel").visible, "Compact music omits metadata and uses a short island");
            check(child("barClockTime").visible, "Compact music keeps the clock visible"); center();
            player.trackArtUrl = Qt.resolvedUrl("test-cover.png");
            const album = child("islandCompactAlbum");
            ready(() => album.visible, "Compact album loads and becomes visible");
            const coverArt = album.children.find(item => item.artworkUrl !== undefined);
            check(coverArt !== undefined && album.radius === 8, "Album uses rounded-square clipping");
            const leftLane = child("islandLeftFlank"), rightLane = child("islandRightFlank");
            const headerClock = child("barClockTime"), headerPeriod = child("barClockPeriod");
            const wave = child("islandCompactWave");
            check(album.width <= leftLane.width && Math.abs(album.x + album.width / 2 - (leftLane.x + leftLane.width / 2)) < .6 && headerClock.x - (album.x + album.width) >= 6, "Compact album centered in left space with clock clearance " + JSON.stringify({albumX:album.x,albumWidth:album.width,laneX:leftLane.x,laneWidth:leftLane.width,clockX:headerClock.x}));
            check(!headerPeriod.visible && rightLane.visible && Math.abs(wave.width - 42) < .1 && Math.abs(wave.x + wave.width / 2 - rightLane.width / 2) < .6 && rightLane.x + wave.x - (headerClock.x + headerClock.width) >= 6, "Compact waveform centered in right space with clock clearance and original width");
            Settings.reducedMotion = false; wait(100);
            check(coverArt.rotation === 0, "Album artwork remains stationary");
            const originArt = album.mapToItem(island.contentItem, 0, 0);
            const originWave = wave.mapToItem(island.contentItem, 0, 0);
            let movingSamples = 0, lastWidth = album.width;
            island.pin("", true); wait(25);
            for (let frame = 0; frame < 12 && movingSamples === 0; frame++) {
                wait(16);
                if (album.width > lastWidth + .1) movingSamples++;
                lastWidth = album.width;
            }
            check(IslandStyle.musicTransition <= 180 && movingSamples >= 1, "Music transition responds quickly and progresses: " + movingSamples + " / " + IslandStyle.musicTransition);
            const middleArt = album.mapToItem(island.contentItem, 0, 0);
            const middleWave = wave.mapToItem(island.contentItem, 0, 0);
            check(island.spectrumDemand && middleArt.y > originArt.y && middleWave.y > originWave.y && album.width > 28 && album.width <= 140, "Artwork and waveform animate globally with continuous spectrum demand");
            island.dismiss(); wait(70);
            check(island.spectrumDemand && album.mapToItem(island.contentItem, 0, 0).y < middleArt.y, "Interrupted morph reverses without losing spectrum " + JSON.stringify({spectrum:island.spectrumDemand,y:album.mapToItem(island.contentItem, 0, 0).y,middle:middleArt.y,activity:island.activity,flanks:island.visual.hasFlanks}));
            wait(350);
            Settings.reducedMotion = true; island.pin("", true); wait(30);
            check(album.width === 140 && child("islandRightFlank").y === 48 && island.spectrumDemand, "Reduced motion reaches final layout immediately");
            island.dismiss(); wait(30);
            check(child("barClockTime").visible, "Clock returns after music hover");
            island.centerRoom = 132; screenInfo.width = 260; wait(20);
            island.pin("", true); wait(350);
            const preview = child("islandMusicPreview");
            const previewPlay = child("islandHeaderMusicPlay");
            check(island.previewPinned && preview.visible && previewPlay.enabled, "Pinned narrow music preview retains functional transport");
            const art=child("islandCompactAlbum"), transport=child("islandExpandedMusicTransport");
            check(art.visible && art.width >= 64 && child("islandRightFlank").y===48 && transport.visible && preview.x >= art.x+art.width+15 && preview.y >= art.y && Math.abs((child("islandRightFlank").y + island.visual.headerInset + child("islandRightFlank").height / 2) - (child("islandMusicMetadata").y + child("islandMusicMetadata").height / 2)) < 4 && child("islandMusicMetadata").x + child("islandMusicMetadata").width <= child("islandRightFlank").x && preview.height === 24 && transport.y >= preview.y+24 && transport.x >= preview.x && transport.x + transport.width <= preview.x+preview.width+.5 && transport.y+transport.height <= island.bodyHeight-12 && !child("islandPreviewFooter").visible, "Artwork and adjacent seek/transport fit inside narrow layout");
            check(!child("barClockTime").visible, "Expanded music hides the clock"); center();
            check(!island.visual.hasFlanks && island.spectrumDemand && island.visual.hasVisibleMediaWave, "Expanded waveform retains demand when narrow header still has room");
            previewPlay.clicked(); wait(30);
            check(!player.isPlaying && island.activity === "media" && preview.visible && previewPlay.enabled && !island.spectrumDemand, "Pausing keeps pinned music preview and resume control while spectrum stops");
            previewPlay.clicked(); wait(30);
            check(player.isPlaying && preview.visible && island.spectrumDemand, "Resume via narrow preview restores visible spectrum demand");
            island.dismiss(); screenInfo.width = 1920; wait(30);
            island.centerRoom = 132; island.pin(); ready(() => island.visual.dashboardReady, "Dashboard destination layout ready"); wait(30);
            check(island.bodyWidth > 420 && Math.abs(island.visual.headerWidth-island.bodyWidth) < .5 && island.visual.surface.y === 0 && island.spectrumDemand, "The entire island grows as a united contour with visible controls spectrum");
            check(child("islandDashboardLoader").item.activeFocus, "Explicit pin focuses the active workspace page");
            check(!child("islandDetails").visible, "Full dashboard replaces the hover glance");
            island.dismiss(); island.centerRoom = 500; wait(20);

            S.IslandEvents.show("volume", "42%", .42, 80, "different-output"); wait(5);
            check(island.activity === "media", "Events only present on their selected output");
            S.IslandEvents.show("volume", "42%", .42, 80, "fixture"); wait(5);
            check(island.activity === "event", "Volume transient overrides persistent activity"); center();
            wait(100); check(island.activity === "media", "Transient expiration restores media");
            island.pin("media"); ready(() => island.visual.dashboardReady, "Dashboard destination layout ready"); wait(30);
            check(island.section === "media" && island.progressDemand && island.spectrumDemand, "Visible Media page requests position updates and spectrum");
            check(island.bodyHeight >= 260 && island.bodyHeight <= island.height, "Media uses its content-sized bounded viewport");
            grabImage(island.contentItem).save("/tmp/sumi-island-expanded.png");
            const play = child("islandDashboardPlay");
            check(play && play.enabled, "Dashboard playback control is available");
            const previous = player.toggles; play.clicked(); wait(5);
            check(player.toggles === previous + 1, "Dashboard playback invokes the selected player");
            player.isPlaying = true;
            island.visual.sectionRequested("controls"); wait(20);
            check(island.section === "controls" && !island.progressDemand, "Changing utility releases hidden media progress work: route=" + island.section + " demand=" + island.progressDemand + " session=" + session.route);
            S.IslandEvents.clear(); wait(180);
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
            check(island.pinned && island.section === "controls" && island.smokeGrab.active, "Notification content growth keeps the current page and focus");
            wait(200);
            check(Math.abs(island.bodyWidth-settledGeometry[0])<.5 && island.bodyHeight<=620, "Notification rows may grow the island inside controls bounds without changing width");
            S.IslandEvents.clear(); S.Notifications.live = ({}); S.Notifications.history = [];
            grabImage(island.contentItem).save("/tmp/sumi-island-controls.png");
            island.visual.sectionRequested("controls"); wait(220);
            check(child("islandDeskControls") !== null || child("islandConnectivityModule") !== null, "Main utility view exposes controls inline");
            check(!child("islandDeskHome") || !child("islandDeskHome").visible, "Main utility view avoids an unnecessary Home page");
            island.dismiss();
            for (const trigger of ["panel", "native", "hidden", "fullscreen", "idle", "output"]) {
                island.leaveHover(); island.pin(); ready(() => island.visual.dashboardReady, "Dashboard destination layout ready"); wait(20);
                if (trigger === "panel") fakeApp.panel = "settings";
                if (trigger === "native") fakeApp.nativeDialogOpen = true;
                if (trigger === "hidden") fakeApp.barVisible = false;
                if (trigger === "fullscreen") island.monitor = {activeWorkspace: {hasFullscreen: true}};
                if (trigger === "idle") island.idle = true;
                if (trigger === "output") island.modelData = null;
                wait(20); check((trigger === "native" || !island.pinned) && !island.smokeGrab.active && !island.spectrumDemand && !island.progressDemand, trigger + " releases interactive work while native handoffs retain their page");
                fakeApp.panel = ""; fakeApp.nativeDialogOpen = false; fakeApp.barVisible = true;
                island.modelData = screenInfo; island.monitor = {activeWorkspace: {hasFullscreen: false}}; island.idle = false; wait(30);
            }
            island.monitor = {activeWorkspace: {hasFullscreen: true}}; wait(20);
            S.IslandEvents.show("volume", "Quiet fullscreen", .4, 1000, "fixture"); wait(10);
            check(!island.visible, "Routine fullscreen feedback stays hidden");
            S.IslandEvents.show("critical-battery", "5% battery", .05, 1000, "fixture"); wait(20);
            check(island.visible && island.expanded && !island.smokeGrab.active, "Critical fullscreen preview never takes keyboard focus");
            S.IslandEvents.dismissCurrent(); wait(20);
            island.pin("inbox"); ready(() => island.visual.dashboardReady, "Dashboard destination layout ready"); wait(30);
            check(island.visible && island.pinned && island.section === "inbox", "Explicit dashboard request works during fullscreen");
            island.dismiss(); island.monitor = {activeWorkspace: {hasFullscreen: false}}; wait(20);
            screenInfo.width = 344; wait(30); island.pin("controls"); ready(() => island.visual.dashboardReady, "Dashboard destination layout ready"); wait(30);
            check(island.bodyWidth <= 320 && island.bodyHeight <= screenInfo.height - 64, "Dashboard adapts to narrow outputs");
            center(); grabImage(island.contentItem).save("/tmp/sumi-island-narrow.png");
            island.dismiss(); screenInfo.width = 1920; wait(30);
            fakeApp.thursdayBackend = assistant;
            assistant.speaking = false; assistant.voiceActive = true; wait(30);
            check(child("islandThursdayCompactOrb").visible && child("islandThursdayCompactOrb").parent.objectName === "islandRightFlank" && !child("islandThursdayHeaderMeter").visible, "Compact Thursday uses the right orb without duplicate meter");
            island.enterHover(); wait(200);
            check(child("islandThursdayHoverOrb").visible && !child("islandThursdayCompactOrb").visible && child("islandThursdayHoverOrb").width >= 100, "Thursday hover uses enlarged right orb without header duplicate");
            const hoverOrb = child("islandThursdayHoverOrb");
            check(Math.abs(hoverOrb.parent.y + hoverOrb.y + hoverOrb.height / 2 - (island.bodyHeight / 2 - 12)) < .6, "Hover orb is visually balanced above the island midpoint");
            island.dismiss(); assistant.voiceActive = false; wait(20);
            fakeApp.thursdayOutputActive = true;
            assistant.speaking = true; wait(30);
            check(island.assistantOutputHere && island.expanded && !island.pinned && !island.smokeGrab.active, "Thursday output expands without keyboard ownership");
            const output = child("islandAssistantOutput");
            check(output.visible && output.answer === assistant.latestAnswer && output.finalTranscript === assistant.finalTranscript, "Automatic speech retains final transcript with actual reply");
            check(!child("islandDashboardFrame").visible, "Automatic reply keeps the cached full workspace hidden");
            check(!child("islandThursdayCompactOrb").visible && child("islandVoiceOrb").visible, "Automatic speech shows only the large body orb");
            const voiceOrb = child("islandVoiceOrb");
            check(Math.abs(output.y + voiceOrb.y + voiceOrb.height / 2 - (island.bodyHeight / 2 - 12)) < .6, "Automatic orb is visually balanced above the island midpoint");
            check(!child("islandWave19").visible && child("barClockTime").visible, "Thursday activity hides media bars while retaining the clock"); center();
            check(!child("islandThursdayHeaderMeter").visible && output.level === .25, "Expanded response orb follows measured playback level");
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
        def chunk(kind, data):
            return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
        pixels = b''.join(b'\x00' + b'\xff\x00\x00\xff' * 64 for _ in range(64))
        (config / 'test-cover.png').write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 64, 64, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))
        runtime = work / 'runtime'; runtime.mkdir(mode=0o700)
        environment = dict(os.environ, SUMI_PREVIEW='1', SUMI_STATE_DIR=str(work / 'state'), QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(['qs', '-p', str(config)], env=environment, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        if result.returncode or 'SUMI_ISLAND_OK' not in output or any(token in output for token in ['TypeError:', 'ReferenceError:', 'Failed to load configuration', 'Unable to assign [undefined]', 'FAIL!', 'Binding loop']):
            raise SystemExit("return=" + str(result.returncode) + "\n" + output)
        print('PASS: outlined black pill/notch; centered clock; hover/pin/focus lifecycle; contextual routes/media; pinned feedback geometry stability; fullscreen critical and explicit access; narrow layout; demand gates; reduced motion')
        print('Native input grab, outside-click delivery and monitor geometry require compositor validation')

if __name__ == '__main__': main()
