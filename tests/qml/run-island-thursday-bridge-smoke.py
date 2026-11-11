#!/usr/bin/env python3
"""Exercise the actual shell's Thursday routing with one passive backend."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

FIXTURES = '''
    QtObject {
        id: fakeThursday
        property bool opened: false
        property bool hudDismissed: true
        property bool connected: true
        property bool ready: true
        property string errorText: ""
        property string voiceError: ""
        property string speechError: ""
        property string outputNotice: ""
        property bool busy: false
        property bool voiceActive: false
        property bool recording: false
        property bool taskActive: false
        property bool sendPending: false
        property string voiceSession: ""
        property string voiceState: "idle"
        property string transcript: ""
        property bool speaking: false
        property bool playbackRunning: false
        property bool speechPreparing: false
        property var currentScreen: null
        property string latestAnswer: ""
        property var confirmations: []
        function openChat() { opened = true; }
    }
    QtObject { id: thursdayLoader; readonly property var item: fakeThursday }
    QtObject { id: codexLoader; readonly property var item: null }
    QtObject {
        id: fakeIsland
        property var modelData: Quickshell.screens[0]
        property bool pinned: false
        property bool previewPinned: false
        property bool idle: false
        property string section: desktopRoot.islandSession.route
        property QtObject visual: QtObject { function focusDefault() {} }
        function prepare(route, fresh) {}
        property int pins: 0
        property int dismissals: 0
        function pin(value) { pins++; if (value) desktopRoot.islandSession.navigate(value); pinned = true; }
        function selectSection(value) { section = value; }
        function promoteDashboard() { previewPinned = false; }
        function dismiss(restore) { dismissals++; pinned = false; }
    }
    QtObject { id: overlays; property var instances: [] }
    QtObject { id: widgetSurface }
'''

TEST = '''
    TestCase {
        name: "IslandThursdayBridge"
        when: true
        function check(value, message) {
            if (!value) { console.error("THURSDAY_BRIDGE_FAILED", message); Qt.exit(1); throw new Error(message); }
        }
        function test_bridge() {
            S.IslandEvents.availableScreens = ["fixture"];
            S.IslandEvents.focusedScreenName = "fixture";
            desktopRoot.registerIsland(fakeIsland);
            fakeThursday.voiceSession = "session-a";
            fakeThursday.recording = true; fakeThursday.voiceActive = true; fakeThursday.voiceState = "listening";
            check(desktopRoot.thursdayOutputActive && !fakeThursday.latestAnswer, "Listening requests automatic preview before any answer");
            fakeThursday.transcript = "Final recognized request"; fakeThursday.recording = false; fakeThursday.voiceActive = false; fakeThursday.voiceState = "submitted";
            check(desktopRoot.thursdayOutputActive && desktopRoot.thursdayOutputUntil > Date.now(), "Final transcript holds preview after recording");
            fakeThursday.transcript = ""; desktopRoot.thursdayOutputUntil = 0;
            fakeIsland.pinned = true; fakeIsland.previewPinned = true;
            desktopRoot.openIsland("controls", null, true);
            check(fakeIsland.pinned && !fakeIsland.previewPinned && fakeIsland.section === "controls", "Matching route promotes a pinned preview instead of closing it");
            fakeIsland.dismiss(false);
            desktopRoot.openIsland("controls", null, false);
            wait(20);
            check(fakeIsland.pinned && fakeIsland.section === "controls", "Control center opens its island page");
            const pins = fakeIsland.pins;
            const dismissed = fakeIsland.dismissals;
            desktopRoot.openIsland("media", null, false);
            check(fakeIsland.pinned && fakeIsland.section === "media" && fakeIsland.pins === pins && fakeIsland.dismissals === dismissed,
                "Changing entry point switches in place without collapsing the island");
            desktopRoot.openIsland("controls", null, true);
            check(fakeIsland.section === "controls" && fakeIsland.pinned, "Right-side settings consistently selects Controls");
            fakeThursday.openChat();
            wait(20);
            check(fakeIsland.pinned && fakeIsland.section === "thursday" && !fakeThursday.opened,
                "Existing Thursday IPC opens the island instead of a duplicate native chat window");
            fakeThursday.openChat();
            wait(20);
            check(!fakeIsland.pinned, "Repeated Thursday toggle closes its island tab");
            desktopRoot.openThursdayFull();
            check(!fakeThursday.opened && !desktopRoot.thursdayExternal && fakeIsland.pinned && fakeIsland.section === "thursday",
                "Full conversation stays within the island without redirect loops");
            desktopRoot.openIsland("controls", null, false);
            wait(20);
            check(!fakeThursday.opened && !desktopRoot.thursdayExternal && fakeIsland.pinned,
                "Returning to island controls closes the full companion");
            fakeThursday.hudDismissed = false;
            check(fakeThursday.hudDismissed, "Voice events cannot create a duplicate legacy HUD");
            S.IslandEvents.clear();
            fakeThursday.confirmations = [{id: "approval-1"}];
            check(S.IslandEvents.eventKind === "thursday" && S.IslandEvents.eventSection === "thursday"
                && fakeThursday.confirmations.length === 1, "Approval attention routes without deciding it " + JSON.stringify({kind:S.IslandEvents.eventKind,enabled:S.IslandEvents.displayEnabled,screen:S.IslandEvents.eventScreenName,screens:S.IslandEvents.availableScreens,external:desktopRoot.thursdayExternal,confirmations:fakeThursday.confirmations}));
            fakeThursday.confirmations = [];
            check(S.IslandEvents.eventKind !== "thursday", "Resolved approvals clear their stale attention preview");
            S.IslandEvents.clear();
            fakeThursday.busy = true;
            fakeThursday.latestAnswer = "Fixture answer";
            fakeThursday.busy = false;
            check(desktopRoot.thursdayOutputActive && desktopRoot.thursdayOutputUntil > Date.now(), "Replies use the text-only output stream, not a duplicate chat window");
            fakeThursday.voiceError = "Fixture voice issue";
            check(S.IslandEvents.eventLabel === "Fixture voice issue", "Assistant failures remain visible when the legacy HUD is suppressed");
            fakeThursday.voiceError = "";
            check(S.IslandEvents.eventLabel !== "Fixture voice issue", "Recovered assistant errors do not block the reply preview");
            desktopRoot.nativeDialogOpen = true;
            const section = fakeIsland.section;
            fakeThursday.openChat();
            wait(20);
            check(!fakeThursday.opened && fakeIsland.section === section, "Native selectors retain focus ownership");
            desktopRoot.nativeDialogOpen = false;
            desktopRoot.unregisterIsland(fakeIsland);
            console.info("THURSDAY_BRIDGE_OK"); Qt.quit();
        }
    }
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-thursday-bridge-") as temporary:
        work = Path(temporary)
        config = work / "shell"
        shutil.copytree(repo / "shell", config)
        source = (config / "shell.qml").read_text()
        source = source.replace("import QtQuick\n", "import QtQuick\nimport QtTest\n", 1)
        source = re.sub(r'^import "(?:ThursdayNative|CodexStatusModule)"[^\n]*\n', "", source, flags=re.M)
        source = re.sub(r"^    // Native assistant integration begins\..*?^    // Native assistant integration ends\.\n", FIXTURES, source, flags=re.M | re.S)
        source = re.sub(r"^    Variants \{.*\n", "", source, flags=re.M)
        source = re.sub(r"^    DesktopWidgets \{.*\n", "", source, flags=re.M)
        source = source[:source.rfind("}")] + TEST + "}\n"
        (config / "shell.qml").write_text(source)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, QT_QPA_PLATFORM="offscreen", SUMI_PREVIEW="1",
                           SUMI_STATE_DIR=str(work / "state"), XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(["qs", "-p", str(config)], env=environment, text=True, capture_output=True, timeout=12)
        output = result.stdout + result.stderr
        if result.returncode or "THURSDAY_BRIDGE_OK" not in output or any(token in output for token in
                ["TypeError:", "ReferenceError:", "Failed to load configuration", "Unable to assign [undefined]", "FAIL!", "Binding loop"]):
            raise SystemExit(output)
        print("PASS: actual shell routes existing Thursday IPC and full inline conversation; one backend/HUD; approvals stay explicit; reply attention; selector guard; in-place control entry points")


if __name__ == "__main__":
    main()
