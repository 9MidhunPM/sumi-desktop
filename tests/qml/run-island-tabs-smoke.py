#!/usr/bin/env python3
"""Render the real tab deck and exercise gesture routing without live hardware."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HARNESS = r'''import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtTest
import Quickshell
import "components"
import "config"
ShellRoot {
    Window {
        id: window
        width: 380; height: 280
        visible: true
        color: "#151519"
        property int requests: 0
        property int verticalEvents: 0
        property int backgroundEvents: 0
        property int buttonClicks: 0
        property int nestedWheels: 0
        property int viewportWheels: 0
        MouseArea { anchors.fill: parent; onClicked: window.backgroundEvents++ }
        IslandTabDeck {
            id: deck
            x: 40; y: 40; width: 300; height: 180
            active: true
            onIndexRequested: index => { window.requests++; currentIndex = index; }
            Rectangle {
                id: home
                color: "#a04040"
                ScrollView {
                    id: childScroll
                    x: 10; y: 10; width: 160; height: 125
                    clip: true
                    contentWidth: availableWidth
                    Flickable {
                        id: childFlick
                        contentWidth: width; contentHeight: 600
                        Column {
                            width: childFlick.width
                            Button { id: childButton; width: 120; height: 34; text: "Click me"; onClicked: window.buttonClicks++ }
                            QuickSlider { id: childSlider; width: 140; height: 40; value: .5; wheelEnabled: true }
                            Item {
                                id: hungryChild
                                width: 140; height: 60
                                MouseArea { anchors.fill: parent; onWheel: wheel => { window.nestedWheels++; wheel.accepted = true; } }
                            }
                            Rectangle { width: 140; height: 450; color: "#603030" }
                        }
                    }
                }
                MouseArea { anchors.fill: parent; z: -1; onWheel: wheel => { if (Math.abs(wheel.angleDelta.y) > Math.abs(wheel.angleDelta.x)) { window.verticalEvents++; wheel.accepted = true; } else wheel.accepted = false; } }
            }
            Rectangle {
                id: inbox
                color: "#40a040"
                MouseArea { anchors.fill: parent; z: -1; onWheel: wheel => { if (Math.abs(wheel.angleDelta.y) > Math.abs(wheel.angleDelta.x)) { window.verticalEvents++; wheel.accepted = true; } else wheel.accepted = false; } }
            }
            Rectangle {
                id: media
                color: "#4040a0"
                MouseArea { anchors.fill: parent; z: -1; onWheel: wheel => { if (Math.abs(wheel.angleDelta.y) > Math.abs(wheel.angleDelta.x)) { window.verticalEvents++; wheel.accepted = true; } else wheel.accepted = false; } }
            }
            Rectangle {
                id: controls
                color: "#a08040"
                MouseArea { anchors.fill: parent; z: -1; onWheel: wheel => { if (Math.abs(wheel.angleDelta.y) > Math.abs(wheel.angleDelta.x)) { window.verticalEvents++; wheel.accepted = true; } else wheel.accepted = false; } }
            }
        }
        IslandTabGesture {
            id: dashboardGesture
            x: 30; y: 20; width: 320; height: 230
            z: 2000
            deck: deck
            active: false
        }
    }
    TestCase {
        name: "IslandTabDeck"
        when: window.visible
        function check(value, label) {
            if (!value) { console.error("ISLAND_TABS_FAILED", label); Qt.exit(1); throw new Error(label); }
        }
        function settle() { wait(240); check(grabImage(deck).alpha(Math.floor(deck.width / 2), Math.floor(deck.height / 2)) === 255, "Deck rendered an opaque page"); }
        function reset(index) {
            deck.consumeHorizontal(0, 0, Qt.ScrollEnd);
            deck.currentIndex = index;
            settle();
            window.requests = 0;
        }
        function onlyCurrent(index) {
            const pages = [home, inbox, media, controls];
            for (let i = 0; i < pages.length; i++) {
                check(pages[i].enabled === (i === index), "Only current page accepts input: " + i);
                check(pages[i].visible === (i === index), "Only current page remains visible after motion: " + i);
            }
            const frame = grabImage(deck);
            const x = Math.floor(deck.width / 2), y = Math.floor(deck.height / 2);
            const colors = [[160, 64, 64], [64, 160, 64], [64, 64, 160], [160, 128, 64]];
            check(frame.red(x, y) === colors[index][0] && frame.green(x, y) === colors[index][1] && frame.blue(x, y) === colors[index][2], "Rendered deck shows the selected page: " + index);
        }
        function test_gestures_and_pages() {
            Theme.effectiveReducedMotion = true;
            settle();
            check(home.width === deck.width && home.height === deck.height, "Pages use available deck geometry");
            onlyCurrent(0);
            mouseClick(childButton, 40, 15);
            check(window.buttonClicks === 1, "Wheel-only overlay lets native button clicks through");
            const sliderBeforeDrag = childSlider.value;
            mouseDrag(childSlider, 35, 20, 55, 0);
            check(Math.abs(childSlider.value - sliderBeforeDrag) > .05, "Wheel-only overlay lets slider pointer dragging through");
            for (const target of [childButton, childSlider, hungryChild, childScroll]) {
                reset(0); childFlick.contentY = 0; childSlider.value = .5;
                const acceptedBefore = window.nestedWheels;
                mouseWheel(target, Math.min(50, target.width / 2), Math.min(20, target.height / 2), -40, 0);
                wait(20);
                check(deck.currentIndex === 1 && window.requests === 1, "Horizontal wheel over nested " + target + " reaches deck first");
                check(childSlider.value === .5 && window.nestedWheels === acceptedBefore, "Horizontal tab gesture is not also delivered to underlying control");
            }
            dashboardGesture.active = true; deck.gestureEnabled = false;
            for (const target of [childButton, childSlider, hungryChild]) {
                reset(0); childFlick.contentY = 0; childSlider.value = .5;
                mouseWheel(target, 40, 18, -40, 0); wait(20);
                check(deck.currentIndex === 1 && window.requests === 1, "Dashboard-wide sibling overlay handles child control " + target);
            }
            reset(0);
            mouseWheel(window.contentItem, 65, 25, -40, 0); wait(20);
            check(deck.currentIndex === 1 && window.requests === 1, "Shared dashboard overlay also handles header area outside the page deck");
            reset(0); childFlick.contentY = 170;
            const scrollBefore = childFlick.contentY;
            mouseWheel(childFlick, 65, 65, 0, -120); wait(100);
            check(childFlick.contentY > scrollBefore && deck.currentIndex === 0, "Vertical wheel passes the front overlay into nested Flickable scrolling");
            childFlick.contentY = 0; settle(); childSlider.value = .5;
            mouseWheel(childSlider, 60, 20, 0, 120); wait(20);
            check(childSlider.value !== .5 && deck.currentIndex === 0, "Vertical wheel retains native slider behavior");
            reset(0);
            dashboardGesture.active = false; deck.gestureEnabled = true;

            // A short swipe crosses at 24 logical pixels, even in a narrow island.
            check(deck.swipeDistance === 24 && deck.wheelDistance === 40, "Short Windows-like gesture distances are the defaults");
            deck.width = 220; reset(1);
            check(deck.consumeHorizontal(-12, 0, Qt.ScrollBegin), "Intentional horizontal gesture is consumed");
            deck.consumeHorizontal(-11, 0, Qt.ScrollUpdate);
            check(deck.currentIndex === 1 && window.requests === 0, "Twenty-three pixels do not switch prematurely");
            deck.consumeHorizontal(-2, 0, Qt.ScrollUpdate);
            check(deck.currentIndex === 2 && window.requests === 1, "Crossing twenty-four pixels selects the next tab");
            deck.consumeHorizontal(-160, 0, Qt.ScrollMomentum);
            deck.consumeHorizontal(-160, 0, Qt.ScrollUpdate);
            check(deck.currentIndex === 2 && window.requests === 1, "Momentum cannot skip multiple tabs in one gesture");
            wait(220);
            deck.consumeHorizontal(-100, 0, Qt.ScrollUpdate);
            check(deck.currentIndex === 2 && window.requests === 1, "A pause during an explicit gesture cannot trigger a second switch");
            deck.consumeHorizontal(0, 0, Qt.ScrollEnd);
            deck.consumeHorizontal(75, 0, Qt.ScrollBegin);
            check(deck.currentIndex === 1 && window.requests === 2, "A new rightward gesture selects previous tab");
            deck.consumeHorizontal(0, 0, Qt.ScrollEnd);

            reset(1);
            check(deck.handleWheel(-12, 1, 0, 0, Qt.ScrollBegin), "Dominant horizontal pixel delta begins a gesture");
            check(!deck.handleWheel(10, 100, 0, 0, Qt.ScrollUpdate), "Mixed vertical delta passes through an ongoing horizontal gesture");
            deck.handleWheel(-13, 1, 0, 0, Qt.ScrollUpdate);
            check(deck.currentIndex === 2 && window.requests === 1, "Vertical detour preserves horizontal accumulation within the gesture");
            deck.handleWheel(0, 0, 0, 0, Qt.ScrollEnd);
            deck.consumeHorizontal(-100, 0, Qt.ScrollMomentum);
            check(deck.currentIndex === 2 && window.requests === 1, "Orphan momentum after the gesture ends cannot navigate");

            reset(1);
            deck.consumeHorizontal(0, -39, Qt.ScrollBegin);
            check(deck.currentIndex === 1, "Thirty-nine angle units stay below the short wheel threshold");
            deck.consumeHorizontal(0, -2, Qt.ScrollUpdate);
            check(deck.currentIndex === 2 && window.requests === 1, "Crossing forty angle units selects the next tab");
            deck.consumeHorizontal(0, 0, Qt.ScrollEnd);

            reset(1);
            deck.consumeHorizontal(-80, 0, Qt.NoScrollPhase);
            deck.consumeHorizontal(-80, 0, Qt.NoScrollPhase);
            check(deck.currentIndex === 2 && window.requests === 1, "Phaseless burst switches once");
            wait(220);
            deck.consumeHorizontal(-80, 0, Qt.NoScrollPhase);
            check(deck.currentIndex === 3 && window.requests === 2, "Quiet gap starts a new phaseless gesture");
            deck.consumeHorizontal(0, 0, Qt.ScrollEnd);

            reset(0);
            deck.consumeHorizontal(100, 0, Qt.ScrollBegin);
            check(deck.currentIndex === 0 && window.requests === 0, "Previous at first tab clamps without a spurious request");
            reset(3);
            deck.consumeHorizontal(-100, 0, Qt.ScrollBegin);
            check(deck.currentIndex === 3 && window.requests === 0, "Next at last tab clamps without wrapping");
            deck.navigate(-1); check(deck.currentIndex === 2, "Navigation helper selects previous tab");
            deck.navigate(10); check(deck.currentIndex === 3, "Navigation helper clamps large positive delta");
            deck.navigate(-10); check(deck.currentIndex === 0, "Navigation helper clamps large negative delta");
            reset(1); deck.forceActiveFocus();
            keyClick(Qt.Key_Tab, Qt.ControlModifier);
            check(deck.currentIndex === 2, "Control Tab selects the next page from deck keyboard focus");
            keyClick(Qt.Key_Tab, Qt.ControlModifier | Qt.ShiftModifier);
            check(deck.currentIndex === 1, "Shift Control Tab selects the previous page");
            reset(0); deck.forceActiveFocus();
            keyClick(Qt.Key_Tab, Qt.ControlModifier | Qt.ShiftModifier);
            check(deck.currentIndex === 0 && window.requests === 0, "Keyboard navigation clamps at the first tab");

            reset(1);
            deck.active = false;
            check(!deck.consumeHorizontal(-100, 0, Qt.ScrollBegin), "Inactive deck does not consume a gesture");
            deck.navigate(1);
            check(deck.currentIndex === 1 && window.requests === 0, "Inactive deck cannot request navigation");
            check(!home.visible && !inbox.visible && !media.visible && !controls.visible
                && !home.enabled && !inbox.enabled && !media.enabled && !controls.enabled, "Inactive deck releases all page visibility and input demand");
            deck.active = true;
            reset(1);
            const beforeVertical = window.verticalEvents;
            mouseWheel(deck, deck.width / 2, deck.height / 2, 0, 120);
            wait(20);
            check(deck.currentIndex === 1 && window.requests === 0 && window.verticalEvents > beforeVertical, "Vertical wheel reaches scrollable page without changing tabs");
            mouseWheel(deck, deck.width / 2, deck.height / 2, 20, 120);
            wait(20);
            check(deck.currentIndex === 1 && window.requests === 0, "Dominantly vertical diagonal movement does not change tabs");
            mouseClick(window.contentItem, 10, 10);
            check(window.backgroundEvents === 1, "Deck does not capture input outside its bounds");

            // Actual rendered interpolation, with outgoing pages disabled.
            deck.width = 300; reset(0);
            Theme.effectiveReducedMotion = false;
            deck.currentIndex = 1;
            let intermediate = false;
            for (let i = 0; i < 8; i++) {
                wait(16);
                const incomingX = inbox.mapToItem(deck, 0, 0).x;
                if (incomingX > .5 && incomingX < deck.width - .5) intermediate = true;
                check(!home.enabled && (!deck.moving || !inbox.enabled), "Sliding pages cannot accept input before transition settles");
            }
            check(intermediate, "Normal transition renders intermediate positions");
            settle(); onlyCurrent(1);
            check(!deck.moving && Math.abs(inbox.mapToItem(deck, 0, 0).x) < .5, "Transition settles at exact selected page");

            Theme.batteryMotion = true;
            deck.currentIndex = 2;
            wait(170);
            check(!deck.moving, "Battery transition completes within the shorter budget");
            onlyCurrent(2);
            Theme.effectiveReducedMotion = true;
            deck.currentIndex = 3;
            wait(20);
            check(!deck.moving && Math.abs(controls.mapToItem(deck, 0, 0).x) < .5, "Reduced motion switches without sliding");
            onlyCurrent(3);
            check(grabImage(deck).alpha(30, 30) === 255, "Final reduced-motion frame rendered");
            console.info("ISLAND_TABS_OK"); Qt.quit();
        }
    }
}
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-island-tabs-") as temporary:
        work = Path(temporary)
        (work / "components").mkdir()
        (work / "config").mkdir()
        for name in ("IslandTabDeck.qml", "IslandTabGesture.qml", "QuickSlider.qml"):
            shutil.copy2(repo / "shell/components" / name, work / "components")
        (work / "config/qmldir").write_text("singleton Theme Theme.qml\n")
        (work / "config/Theme.qml").write_text("pragma Singleton\nimport QtQuick\nQtObject { property bool effectiveReducedMotion: false; property bool batteryMotion: false; property color textMain: \"#eeeeee\"; property color textSoft: \"#bbbbbb\"; property color accentBlue: \"#7788aa\"; property color desktopBackground: \"#111111\"; property int motionControl: 0 }\n")
        (work / "shell.qml").write_text(HARNESS)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime), SUMI_PREVIEW="1")
        result = subprocess.run(["qs", "-p", str(work)], env=environment, text=True, capture_output=True, timeout=15)
        output = result.stdout + result.stderr
        errors = ("TypeError:", "ReferenceError:", "Unable to assign [undefined]", "Failed to load configuration", "FAIL!", "Binding loop")
        if result.returncode or "ISLAND_TABS_OK" not in output or any(error in output for error in errors):
            raise SystemExit(output)
        print("PASS: horizontal thresholds/signs/phases and CtrlTab; one switch per momentum gesture; full-surface dispatch across nested controls; vertical/click/drag passthrough; edge clamp; inactive input; rendered normal/battery/reduced transitions; page input isolation")
        print("Physical touchpad gestures still require native hardware validation")


if __name__ == "__main__":
    main()
