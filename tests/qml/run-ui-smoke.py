#!/usr/bin/env python3
"""Load all panel content without a compositor or the host desktop session.

Quickshell PanelWindow requires a Wayland/X11 backend, which Qt's offscreen
plugin does not provide. This harness replaces only the outer native window
wrappers in a temporary copy with ordinary QtQuick Windows. It exercises the
real panel content, service bindings, and root panel/focus lifecycle. Native
layer-shell geometry and keyboard ownership still require a host-session QA.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-ui-smoke-") as temporary:
        work = Path(temporary)
        config = work / "shell"
        shutil.copytree(repo / "shell", config)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        for filename in ("Bar.qml", "Overlay.qml", "NotificationToasts.qml"):
            path = config / filename
            source = path.read_text().replace("PanelWindow {", "Window {", 1)
            source = re.sub(r"^    (screen:|anchors \{|margins \{|exclusiveZone:|exclusionMode:|mask:|WlrLayershell\.).*\n", "", source, flags=re.M)
            source = re.sub(r"^    implicit(Width|Height):", lambda match: "    " + match[1].lower() + ":", source, flags=re.M)
            source = source.replace("app.activeScreen === screen", "app.activeScreen === modelData")
            if filename in ("Bar.qml", "Overlay.qml"):
                source = source.replace("    color: \"transparent\"", "    width: 1440\n" + ("    height: 900\n" if filename == "Overlay.qml" else "") + "    color: \"transparent\"", 1)
            if filename == "Overlay.qml":
                probe = '''
    Timer {
        interval: 100
        running: overlay.visible
        repeat: true
        onTriggered: {
            if (page.item) {
                console.info("SUMI_UI_CONTENT", overlay.app.panel);
                if (overlay.app.panel === "appearance") {
                    const metrics = {themeCount: page.item.themeCount, galleryWidth: page.item.galleryWidth, previewWidth: page.item.previewWidth};
                    overlay.app.smokeAppearanceMetrics = JSON.stringify(metrics);
                    if (metrics.themeCount >= 22 && metrics.galleryWidth > 200 && metrics.previewWidth <= 260 && metrics.previewWidth > 0) {
                        overlay.app.smokeAppearanceChecked = true;
                        console.info("SUMI_APPEARANCE_LAYOUT_OK", JSON.stringify(metrics));
                    }
                }
            }
        }
    }
'''
                source = source[:source.rfind("}")] + probe + "}\n"
            path.write_text(source)
        path = config / "shell.qml"
        source = path.read_text()
        # The dedicated widget harness exercises its real content and layout.
        # This runner replaces the older native wrappers for panel lifecycle QA.
        source = source.replace("    DesktopWidgets { id: widgetSurface; modelData: desktopRoot.widgetScreen; app: desktopRoot }\n", "    QtObject { id: widgetSurface; property bool visible: false; property bool idle: false; property bool occluded: false; property bool moving: false; property var geometry: ({}) }\n")
        source = re.sub(r'^import "(?:ThursdayNative|CodexStatusModule)"[^\n]*\n', "", source, flags=re.M)
        source = re.sub(r"^    // Native assistant integration begins\..*?^    // Native assistant integration ends\.\n", "    QtObject { id: codexLoader; readonly property var item: null }\n", source, flags=re.M | re.S)
        source = re.sub(r"^    LazyLoader \{ id: thursdayLoader;[^\n]*\n", "", source, flags=re.M)
        source = re.sub(r"^    LazyLoader \{ id: codexLoader;[^\n]*\n", "    QtObject { id: codexLoader; readonly property var item: null }\n", source, flags=re.M)
        test = '''
    property int smokePhase: 0
    property bool smokeAppearanceChecked: false
    property double smokeAppearanceDeadline: 0
    property string smokeAppearanceMetrics: "Appearance has not loaded"
    property var smokePanels: ["launcher", "files", "clipboard", "appearance", "widgets", "settings", "calendar", "media", "notifications", "pomodoro", "help", "power"]
    Timer {
        interval: 750
        running: true
        repeat: true
        onTriggered: {
            if (desktopRoot.panel === "appearance" && !desktopRoot.smokeAppearanceChecked) {
                if (Date.now() > desktopRoot.smokeAppearanceDeadline) {
                    console.error("SUMI_APPEARANCE_LAYOUT_FAILED", desktopRoot.smokeAppearanceMetrics);
                    Qt.exit(4);
                }
                return;
            }
            if (desktopRoot.smokePhase < desktopRoot.smokePanels.length) {
                const panelName = desktopRoot.smokePanels[desktopRoot.smokePhase];
                desktopRoot.open(panelName, null);
                if (panelName === "appearance") {
                    desktopRoot.smokeAppearanceDeadline = Date.now() + 5000;
                    desktopRoot.nativeDialogOpen = true;
                    desktopRoot.toggle("appearance", null);
                    desktopRoot.close();
                    desktopRoot.open("launcher", null);
                    desktopRoot.thursdayToggle();
                    desktopRoot.codexToggle(null);
                    if (desktopRoot.panel !== "appearance" || !desktopRoot.nativeDialogOpen) {
                        console.error("SUMI_NATIVE_DIALOG_HANDOFF_FAILED"); Qt.exit(5); return;
                    }
                    desktopRoot.nativeDialogOpen = false;
                }
                console.info("SUMI_UI_PANEL", panelName);
                if (panelName === "pomodoro") {
                    desktopRoot.focusReset(5);
                    desktopRoot.focusStart();
                    if (!desktopRoot.focusRunning || desktopRoot.focusDeadline <= Date.now()) Qt.exit(2);
                    desktopRoot.focusPause();
                    if (desktopRoot.focusRunning || desktopRoot.focusRemaining <= 0) Qt.exit(3);
                    desktopRoot.focusReset(25);
                }
                desktopRoot.smokePhase += 1;
            } else {
                desktopRoot.close();
                console.info("SUMI_UI_SMOKE_OK");
                Qt.quit();
            }
        }
    }
'''
        path.write_text(source[:source.rfind("}")] + test + "}\n")
        environment = dict(os.environ, SUMI_PREVIEW="1", SUMI_STATE_DIR=str(work / "state"), SUMI_DESKTOPCTL=str(repo / "bin/desktopctl"), QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(["qs", "-p", str(config)], env=environment, text=True, capture_output=True, timeout=20)
        output = result.stdout + result.stderr
        if result.returncode or "SUMI_UI_SMOKE_OK" not in output or any(message in output for message in ("TypeError:", "ReferenceError:", "Failed to load configuration", "Unable to assign [undefined]")):
            raise SystemExit(output)
        for panel in ("launcher", "files", "clipboard", "appearance", "widgets", "settings", "calendar", "media", "notifications", "pomodoro", "help", "power"):
            if f"SUMI_UI_CONTENT {panel}" not in output:
                raise SystemExit(f"Panel {panel} did not instantiate\n{output}")
        if "SUMI_APPEARANCE_LAYOUT_OK" not in output:
            raise SystemExit(f"Appearance catalog and gallery dimensions were not verified\n{output}")
        print("PASS: all 12 panel views instantiate; service bindings; panel navigation; focus start/pause/reset")
        print("PASS: Appearance loads at least 22 themes; gallery remains wider than 200px; preview stays within 260px")
        print("Native PanelWindow wrappers replaced only in temporary test copy; compositor QA remains required")


if __name__ == "__main__":
    main()
