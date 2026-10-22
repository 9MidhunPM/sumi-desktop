#!/usr/bin/env python3
"""Sample actual popup/toast frames without a compositor or desktop mutations."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "config"
import "services" as S
ShellRoot {
    QtObject { id: screenInfo; property int width: 1440; property int height: 900 }
    QtObject {
        id: fakeApp
        property string panel: ""
        property bool nativeDialogOpen: false
        property var activeScreen: screenInfo
        property var notificationScreen: screenInfo
        property int activationSerial: 0
        property string settingsSection: ""
        property bool focusRunning: false
        property double focusRemaining: 1500000
        property double focusDeadline: 0
        function open(name, screen) { panel = name; activationSerial++; }
        function close() { panel = ""; }
        function focusStart() {} function focusPause() {} function focusReset(minutes) {}
    }
    Overlay { id: overlay; app: fakeApp; modelData: screenInfo }
    NotificationToasts { id: toasts; app: fakeApp }
    TestCase {
        name: "SumiPopupMotion"
        when: true
        function check(condition, message) {
            if (!condition) { console.error("SUMI_POPUP_MOTION_FAILED", message); Qt.exit(1); throw new Error(message); }
        }
        function ready(condition, label) {
            let elapsed = 0;
            while (!condition() && elapsed < 1500) { wait(8); elapsed += 8; }
            check(condition(), label);
        }
        function within(item, ancestor) {
            while (item) { if (item === ancestor) return true; item = item.parent; }
            return false;
        }
        function animatePanel(name, battery) {
            Settings.reducedMotion = false;
            Motion.battery = battery;
            check(Theme.motionEnter > 0 && Theme.motionExit > 0, "Normal and battery motion remain animated");
            fakeApp.open(name, screenInfo);
            overlay.requestActivate();
            const panel = overlay.smokeItem;
            const loader = panel.parent;
            let entering = false;
            let previous = 0;
            for (let elapsed = 0; elapsed < Theme.motionEnter + 48; elapsed += 16) {
                wait(16);
                const progress = loader.motionProgress;
                check(progress >= previous - 0.001 && progress <= 1, name + " enters without a jump or overshoot");
                previous = progress;
                if (progress > 0.01 && progress < 0.98) {
                    entering = true;
                    check(loader.scale > 0.95 && loader.scale < 1, name + " has visible intermediate scale");
                    check(Math.abs(loader.transform[0].x) + Math.abs(loader.transform[0].y) > 0.1, name + " glides during entry");
                    check(within(overlay.activeFocusItem, panel), "Keyboard focus arrives before " + name + " settles");
                    check(overlay.smokeInputWidth === overlay.width && overlay.smokeKeyboardExclusive, "Opening owns input while animating");
                }
            }
            check(entering, name + " has actual intermediate entry frames in " + (battery ? "battery" : "normal") + " mode");
            check(loader.motionProgress === 1 && loader.opacity === 1 && loader.scale === 1 && loader.transform[0].x === 0 && loader.transform[0].y === 0, name + " settles at its original geometry");
            fakeApp.nativeDialogOpen = true; wait(1);
            check(overlay.visible && overlay.smokeInputWidth === 0 && !overlay.smokeKeyboardExclusive && overlay.smokeScrimOpacity === 0, "Native picker releases input immediately without unmapping its parent");
            fakeApp.nativeDialogOpen = false;
            fakeApp.close();
            check(overlay.smokeInputWidth === 0 && !overlay.smokeKeyboardExclusive && !loader.enabled, "Close releases input before the exit animation");
            let exiting = false;
            previous = 1;
            for (let elapsed = 0; elapsed < Theme.motionExit + 48; elapsed += 16) {
                wait(16);
                const progress = loader.motionProgress;
                check(progress <= previous + 0.001 && progress >= 0, name + " exits smoothly");
                previous = progress;
                if (progress > 0.01 && progress < 0.98) {
                    exiting = true;
                    check(overlay.visible && loader.visible && loader.scale < 1, "Closing surface remains mapped for its visible exit frames");
                }
            }
            check(exiting && loader.motionProgress === 0 && !loader.visible && !overlay.visible, name + " completes its animated exit: intermediate=" + exiting + " progress=" + loader.motionProgress + " loader=" + loader.visible + " surface=" + overlay.visible + " scrim=" + overlay.reveal);
        }
        function test_motion() {
            ready(() => !Settings.loading, "Settings loaded");
            Settings.reducedMotion = true;
            for (const name of ["launcher", "settings", "calendar"]) {
                fakeApp.open(name, screenInfo);
                ready(() => overlay.smokeItem !== null, name + " preloads");
                wait(16);
                fakeApp.close(); wait(16);
            }
            for (const name of ["launcher", "settings", "calendar"]) animatePanel(name, false);
            animatePanel("settings", true);
            Motion.battery = false;
            fakeApp.open("launcher", screenInfo); wait(48);
            const loader = overlay.smokeItem.parent;
            const opening = loader.motionProgress;
            fakeApp.close(); wait(16);
            check(loader.motionProgress <= opening && loader.motionProgress > 0, "Interrupted entry reverses from its current frame");
            const closing = loader.motionProgress;
            fakeApp.open("launcher", screenInfo); wait(16);
            check(loader.motionProgress >= closing && loader.motionProgress < 1, "Reopening reverses the exit without snapping");
            wait(Theme.motionEnter + 32);
            Settings.reducedMotion = true;
            fakeApp.close(); wait(1);
            check(loader.motionProgress === 0 && !overlay.visible && overlay.smokeInputWidth === 0, "Reduced motion closes immediately");
            fakeApp.open("launcher", screenInfo); wait(1);
            check(loader.motionProgress === 1 && loader.scale === 1 && loader.transform[0].x === 0 && loader.transform[0].y === 0, "Reduced motion opens at the settled geometry");
            fakeApp.close(); wait(1);

            Settings.reducedMotion = false;
            const first = {id: 801, appName: "Motion fixture", summary: "First card", body: "Notification slide", actions: [], popup: true};
            const second = Object.assign({}, first, {id: 802, summary: "Second card"});
            S.Notifications.history = [first];
            ready(() => toasts.smokeList.itemAtIndex(0) !== null, "First toast instantiates");
            let toastEntry = false;
            for (let elapsed = 0; elapsed < Theme.motionEnter + 48; elapsed += 16) {
                wait(16);
                if (toasts.reveal > 0.01 && toasts.reveal < 0.98) {
                    toastEntry = true;
                    check(toasts.smokeList.transform[0].x > 0 && toasts.smokeList.scale < 1, "First toast slides and scales into place");
                    check(toasts.height >= toasts.smokeList.itemAtIndex(0).height - 1, "First card is not clipped by an expanding native surface");
                }
            }
            check(toastEntry && toasts.reveal === 1 && toasts.smokeList.transform[0].x === 0 && toasts.smokeList.scale === 1, "First toast has intermediate and settled frames");
            S.Notifications.history = [first, second];
            ready(() => toasts.smokeList.itemAtIndex(1) !== null, "Second toast instantiates");
            let inserted = false;
            for (let elapsed = 0; elapsed < Theme.motionEnter + 48; elapsed += 16) {
                wait(16);
                const item = toasts.smokeList.itemAtIndex(1);
                if (item.opacity > 0.01 && item.opacity < 0.98) {
                    inserted = true;
                    check(item.transform[0].x > 0 && item.scale < 1, "Inserted toast slides into the existing stack");
                    check(toasts.height >= item.y + item.height - toasts.smokeList.contentY - 1, "Added card has its full viewport throughout entry");
                }
            }
            check(inserted, "Insertion transition has intermediate frames");
            const removed = toasts.smokeList.itemAtIndex(0);
            S.Notifications.history = [second];
            let removal = false;
            for (let elapsed = 0; elapsed < Theme.motionExit + Theme.motionEnter + 48; elapsed += 16) {
                wait(16);
                if (removed && removed.opacity > 0.01 && removed.opacity < 0.98) { removal = true; check(removed.transform[0].x > 0 && removed.scale < 1 && !removed.enabled, "Removed toast slides out without accepting another action"); }
            }
            check(removal, "Removal transition has intermediate frames");
            const remaining = toasts.smokeList.itemAtIndex(0);
            check(Math.abs(remaining.y - toasts.smokeList.contentY) < 1 && toasts.height >= remaining.height - 1, "Remaining toast settles visibly after removal");
            const lastHeight = toasts.height;
            S.Notifications.history = [];
            let toastExit = false;
            for (let elapsed = 0; elapsed < Theme.motionExit + 48; elapsed += 16) {
                wait(16);
                if (toasts.reveal > 0.01 && toasts.reveal < 0.98) {
                    toastExit = true;
                    check(toasts.visible && toasts.height >= lastHeight - 1 && toasts.smokeList.transform[0].x > 0, "Last toast retains its surface while sliding out");
                }
            }
            check(toastExit && !toasts.visible && toasts.smokeCount === 0, "Final toast exit settles and unmaps");
            Settings.reducedMotion = true;
            S.Notifications.history = [first]; wait(16);
            check(toasts.reveal === 1 && toasts.smokeList.scale === 1 && toasts.smokeList.transform[0].x === 0, "Reduced motion toast appears immediately");
            S.Notifications.history = []; wait(16);
            check(!toasts.visible && toasts.smokeCount === 0, "Reduced motion toast disappears immediately");
            console.info("SUMI_POPUP_MOTION_OK"); Qt.quit();
        }
    }
}
'''


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-popup-motion-") as temporary:
        work = Path(temporary)
        config = work / "shell"
        shutil.copytree(repo / "shell", config)
        for filename in ("Overlay.qml", "NotificationToasts.qml"):
            path = config / filename
            source = path.read_text().replace("PanelWindow {", "Window {", 1)
            source = re.sub(r"^    (screen:|anchors \{|margins \{|exclusiveZone:|exclusionMode:|WlrLayershell\.).*\n", "", source, flags=re.M)
            if filename == "Overlay.qml":
                source = source.replace('    mask: Region { width: overlay.popupShown && !overlay.app.nativeDialogOpen ? overlay.width : 0; height: overlay.popupShown && !overlay.app.nativeDialogOpen ? overlay.height : 0 }', '    readonly property real smokeInputWidth: overlay.popupShown && !overlay.app.nativeDialogOpen ? overlay.width : 0')
                source = source.replace('    color: "transparent"', '''    width: modelData.width
    height: modelData.height
    readonly property var smokeItem: page.item
    readonly property real smokeScrimOpacity: scrim.opacity
    readonly property bool smokeKeyboardExclusive: popupShown && !app.nativeDialogOpen
    color: "transparent"''', 1)
            else:
                source = re.sub(r"^    implicit(Width|Height):", lambda match: "    " + match[1].lower() + ":", source, flags=re.M)
                source = source.replace('    color: "transparent"', '''    readonly property var smokeList: toastList
    readonly property int smokeCount: toastModel.count
    color: "transparent"''', 1)
            path.write_text(source)
        motion = config / "config/Motion.qml"
        source = motion.read_text()
        source, count = re.subn(r"^    readonly property bool battery:.*$", "    property bool battery: false", source, count=1, flags=re.M)
        if count != 1:
            raise SystemExit("Motion battery fixture injection needs updating")
        motion.write_text(source)
        (config / "shell.qml").write_text(HARNESS)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, SUMI_PREVIEW="1", SUMI_STATE_DIR=str(work / "state"), SUMI_DESKTOPCTL=str(repo / "bin/desktopctl"), QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(["qs", "-p", str(config)], env=environment, capture_output=True, text=True, timeout=12)
        output = result.stdout + result.stderr
        if result.returncode or "SUMI_POPUP_MOTION_OK" not in output or any(message in output for message in ("TypeError:", "ReferenceError:", "Failed to load configuration", "Unable to assign [undefined]", "FAIL!", "Binding loop")):
            raise SystemExit(output)
        print("PASS: actual intermediate panel glide/scale and exit frames; normal/battery/reduced modes; interrupted reversal; immediate focus/mask handoff; toast entry/insertion/removal/exit with full-height surface")


if __name__ == "__main__":
    main()
