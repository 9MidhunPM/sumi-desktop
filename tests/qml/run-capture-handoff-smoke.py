#!/usr/bin/env python3
"""Exercise the exact shell capture handoff with isolated controller replies."""
import os
from pathlib import Path
import runpy
import re
import shutil
import subprocess
import tempfile

HARNESS = r'''import QtQuick
import QtTest
import Quickshell
import "services" as S
import "config"
ShellRoot {
    id: desktopRoot
    S.IslandSession { id: islandSession }
    readonly property alias islandSession: islandSession
    property var islandWindows: [island]
    property var captureReturn: null
    property string annotationId: ""
    property bool annotationChecking: false
    property var activeScreen: screenInfo
    function openIsland(route, screen, toggle) { if (route) islandSession.navigate(route); island.pin(); }
    property bool nativeDialogOpen: false
    property bool captureSelecting: false
    property string panel: ""
    property bool focusRunning: false
    property double focusDeadline: 0
    property double focusRemaining: 1500000
    property var notificationScreen: screenInfo
    QtObject { id: screenInfo; property string name: "fixture"; property int width: 1920; property int height: 1080 }
    property bool barVisible: true
    property int closes: 0
    function close() { closes++; panel = ""; island.dismiss(); }
    __CAPTURE_HANDOFF__
    DynamicIsland { id: island; app: desktopRoot; modelData: screenInfo; centerRoom: 500 }
    Window {
        id: win
        visible: true; width: 160; height: 80

        TestCase {
            name: "CaptureHandoff"
            when: win.visible
            function check(value, message) { if (!value) { console.error("CAPTURE_HANDOFF_FAILED", message); Qt.exit(1); throw new Error(message); } }
            function requests(name) { return S.Desktop.requests.filter(item => item.name === name); }
            function begin(annotate, record) {
                if (record) S.Recording.recording = false;
                desktopRoot.selectCapture(annotate, record);
                check(desktopRoot.nativeDialogOpen && island.visible, "Region handoff keeps the compact island visible");
                const before = S.Desktop.requests.length;
                desktopRoot.selectCapture(false, false);
                check(S.Desktop.requests.length === before, "A second selector cannot start during a handoff");
                wait(130);
                check(desktopRoot.nativeDialogOpen && island.visible, "Pending region selection cannot make the bar disappear");
                check(!island.pinned && !island.expanded && island.activity === "capture"
                    && Math.abs(island.bodyHeight - (island.notch ? 46 : 42)) < 0.1
                    && island.inputWidth === 0 && island.inputHeight === 0,
                    "Selector retains focus while the island is compact and passes input through");
            }
            function released(label) {
                check(!desktopRoot.nativeDialogOpen && island.visible && desktopRoot.barVisible, label + " releases the actual root visibility guard");
            }
            function test_handoff() {
                wait(40);
                Settings.reducedMotion = true;
                S.IslandEvents.availableScreens = ["fixture"];
                S.IslandEvents.focusedScreenName = "fixture";
                S.IslandEvents.clear();
                island.idle = false;
                island.monitor = {activeWorkspace: {hasFullscreen:false}};
                begin(false, true);
                check(requests("record").length === 1 && requests("record")[0].args[0] === "start"
                    && requests("capture").length === 0, "Root Timer dispatches record=true to real Recording.start");
                S.Desktop.respond("record", true, {recording:true,file:"/tmp/fixture.mp4"});
                released("Successful recording start");
                check(S.Recording.recording && !S.Recording.busy, "Recording state confirms the live result");

                begin(false, true);
                S.Desktop.respond("record", true, {recording:false,cancelled:true});
                released("Cancelled recording selection");
                check(!S.Recording.recording && !S.Recording.busy, "Cancellation creates no active recording");

                begin(false, true);
                S.Desktop.respond("record", false, {}, "Recorder launch failed");
                released("Failed recording start");
                wait(20);
                check(S.IslandEvents.eventLabel === "Recorder launch failed", "Failure feedback publishes after guard release");
                S.Desktop.respond("record", true, {recording:false});

                begin(false, true);
                S.Desktop.respond("record", true, {});
                released("Malformed successful recording reply");
                S.Desktop.respond("record", true, {recording:false});

                S.Recording.busy = true;
                desktopRoot.selectCapture(false, true); wait(130);
                released("Busy recording control rejection");
                check(requests("record").length === 0, "Busy service rejection starts no selector");
                S.Recording.busy = false;

                begin(true, false);
                check(requests("capture").length === 1 && requests("capture")[0].args.join() === "region,annotate", "Screenshot annotation dispatch stays separate from recording");
                S.Desktop.respond("capture", true, {saved:true,file:"/tmp/fixture.png"});
                released("Successful screenshot");

                begin(true, false);
                S.Desktop.respond("capture", true, {saved:true,file:"/tmp/fixture.png",annotation_id:"annotation-fixture"});
                check(desktopRoot.nativeDialogOpen && desktopRoot.captureSelecting && desktopRoot.annotationId === "annotation-fixture", "Annotation editor retains the native handoff after region selection");
                wait(750);
                check(requests("annotation-status").length === 1, "Annotation handoff checks owned editor status");
                S.Desktop.respond("annotation-status", true, {active:true});
                check(desktopRoot.nativeDialogOpen, "An active annotation editor retains focus ownership");
                wait(750);
                S.Desktop.respond("annotation-status", true, {active:false});
                released("Annotation editor completion");

                begin(false, false);
                S.Desktop.respond("capture", false, {}, "Screenshot cancelled");
                released("Cancelled screenshot");

                begin(false, false);
                const previous = requests("capture")[0];
                S.Desktop.requests = [];
                wait(20);
                released("Completed request whose callback was lost");
                desktopRoot.nativeDialogOpen = true;
                previous.callback(true, {saved:true}, "");
                check(desktopRoot.nativeDialogOpen, "A late capture callback cannot release an unrelated native dialog");
                desktopRoot.nativeDialogOpen = false;
                begin(false, false);
                previous.callback(true, {saved:true}, "");
                check(desktopRoot.nativeDialogOpen, "A stale callback cannot release a newer selector");
                S.Desktop.respond("capture", true, {saved:true});
                released("New selection after lost callback");

                desktopRoot.nativeDialogOpen = true;
                wait(20);
                check(!island.visible, "Unrelated native dialogs retain their existing overlay guard");
                desktopRoot.nativeDialogOpen = false;

                desktopRoot.panel = "settings";
                begin(false, false);
                check(desktopRoot.panel === "", "Standalone settings closes before region selector");
                S.Desktop.respond("capture", false, {}, "Screenshot cancelled");
                released("Standalone settings capture cancellation");

                S.IslandEvents.clear();
                islandSession.navigate("capture");
                island.pin(); wait(40);
                check(island.pinned, "Capture starts from an actually pinned origin");
                const originRevision = islandSession.revision;
                begin(false, false);
                S.Desktop.respond("capture", false, {}, "desktopctl: Screenshot cancelled");
                check(desktopRoot.nativeDialogOpen && !island.pinned, "Selector teardown keeps input guarded before restoring origin");
                wait(45);
                island.smokeGrab.cleared();
                wait(160);
                check(island.pinned && island.section === "capture" && islandSession.revision === originRevision,
                    "Selector cancellation repins the origin after delayed native grab-clear");
                check(!desktopRoot.nativeDialogOpen && !desktopRoot.captureSelecting && !S.IslandEvents.active,
                    "Ordinary Escape cancellation restores controls without an error alert");
                island.dismiss();
                S.Desktop.preview = true;
                desktopRoot.selectCapture(false, true); wait(130);
                released("Preview recording rejection");
                console.info("CAPTURE_HANDOFF_OK"); Qt.quit();
            }
        }
    }
}
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    source = (repo / "shell/shell.qml").read_text()
    start = source.index("    function selectCapture(")
    end = source.index("    property var activeScreen:", start)
    handoff = source[start:end]
    fake_desktop = runpy.run_path(str(repo / "tests/qml/run-quick-settings-smoke.py"))["DESKTOP"]
    with tempfile.TemporaryDirectory(prefix="sumi-capture-handoff-") as temporary:
        work = Path(temporary)
        shutil.copytree(repo / "shell", work, dirs_exist_ok=True)
        services = work / "services"
        (services / "Desktop.qml").write_text(fake_desktop.replace('property var requests: []', 'property var requests: []\nreadonly property int pendingCount: requests.length'))
        adapter = runpy.run_path(str(repo / "tests/qml/run-island-smoke.py"))["adapt"]
        path = work / "DynamicIsland.qml"
        path.write_text(adapter(path.read_text()))
        visual = work / "components/IslandContent.qml"
        visual.write_text(visual.read_text().replace('HoverHandler {', 'HoverHandler { enabled: false;'))
        (work / "shell.qml").write_text(HARNESS.replace("__CAPTURE_HANDOFF__", handoff))
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime), SUMI_PREVIEW="1", SUMI_STATE_DIR=str(work / "state"))
        result = subprocess.run(["qs", "-p", str(work)], env=environment, text=True, capture_output=True, timeout=12)
        output = result.stdout + result.stderr
        errors = ("TypeError:", "ReferenceError:", "Unable to assign [undefined]", "Failed to load configuration", "FAIL!", "Binding loop")
        if result.returncode or "CAPTURE_HANDOFF_OK" not in output or any(error in output for error in errors):
            raise SystemExit(output)
        print("PASS: actual root record/capture dispatch; compact inputless selector handoff; success/cancel/error/malformed/busy/preview release; lost/stale callback recovery; other native dialog guard; selector serialization; pinned origin restoration after delayed grab-clear; silent cancellation")
        print("Controller and recorder are inert; native region selection is not exercised")


if __name__ == "__main__":
    main()
