#!/usr/bin/env python3
"""Exercise every legacy entry point inside the actual island workspace."""
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import tempfile

PROBE = '''
    DynamicIsland { id: smokeIsland; app: desktopRoot; modelData: Quickshell.screens[0]; idle: false; monitor: ({activeWorkspace:{hasFullscreen:false}}) }
    property int smokePhase: -1
    property var smokePanels: ["launcher", "files", "clipboard", "appearance", "widgets", "settings", "calendar", "media", "notifications", "pomodoro", "help", "power"]
    Timer {
        interval: 550; running: true; repeat: true
        onTriggered: {
            if (desktopRoot.smokePhase >= 0) {
                const name = desktopRoot.smokePanels[desktopRoot.smokePhase];
                const page = smokeIsland.visual.deskItem.currentPage;
                if (name === "settings") {
                    if (desktopRoot.panel !== "settings" || desktopRoot.settingsSection !== "" || smokeIsland.pinned) { console.error("SUMI_UI_CONTENT_FAILED", name); Qt.exit(2); return; }
                    desktopRoot.openSettings("wifi", null);
                    if (desktopRoot.panel !== "settings" || desktopRoot.settingsSection !== "wifi" || !S.Network.discoveryRequested || S.Bluetooth.discoveryRequested) { console.error("SUMI_WIFI_ROUTING_FAILED"); Qt.exit(2); return; }
                    const priorActivation = desktopRoot.activationSerial;
                    desktopRoot.openSettings("wifi", null);
                    if (desktopRoot.activationSerial !== priorActivation + 1 || !S.Network.discoveryRequested) { console.error("SUMI_WIFI_REPEAT_FAILED"); Qt.exit(2); return; }
                    desktopRoot.openSettings("bluetooth", null);
                    if (desktopRoot.settingsSection !== "bluetooth" || S.Network.discoveryRequested || !S.Bluetooth.discoveryRequested) { console.error("SUMI_BLUETOOTH_ROUTING_FAILED"); Qt.exit(2); return; }
                    desktopRoot.openSettings("audio", null);
                    if (desktopRoot.settingsSection !== "audio" || S.Network.discoveryRequested || S.Bluetooth.discoveryRequested) { console.error("SUMI_AUDIO_ROUTING_FAILED"); Qt.exit(2); return; }
                    desktopRoot.toggle("settings", null);
                    if (desktopRoot.panel !== "") { console.error("SUMI_SETTINGS_TOGGLE_FAILED"); Qt.exit(2); return; }
                    smokeIsland.visual.headerClicked();
                    if (desktopRoot.panel !== "settings" || desktopRoot.settingsSection !== "") { console.error("SUMI_CLOCK_SETTINGS_FAILED"); Qt.exit(2); return; }
                    smokeIsland.visual.headerClicked();
                    if (desktopRoot.panel !== "") { console.error("SUMI_CLOCK_TOGGLE_FAILED"); Qt.exit(2); return; }
                    desktopRoot.nativeDialogOpen = true;
                    smokeIsland.visual.headerClicked();
                    if (desktopRoot.panel !== "") { console.error("SUMI_CLOCK_DIALOG_GUARD_FAILED"); Qt.exit(2); return; }
                    desktopRoot.nativeDialogOpen = false;
                } else if (!page || !page.active || !smokeIsland.pinned) { console.error("SUMI_UI_CONTENT_FAILED", name); Qt.exit(2); return; }
                console.info("SUMI_UI_CONTENT", name);
                if (name === "appearance") {
                    const loader = probe.findChild(page, "islandDesktopAppearanceLoader");
                    const view = loader && loader.item;
                    const metrics = view ? {themeCount:view.themeCount,galleryWidth:view.galleryWidth,previewWidth:view.previewWidth} : {};
                    if (!view || metrics.themeCount < 22 || metrics.galleryWidth <= 100 || metrics.previewWidth <= 0 || metrics.previewWidth > smokeIsland.bodyWidth) {
                        console.error("SUMI_APPEARANCE_LAYOUT_FAILED",JSON.stringify(metrics), "route",page.route,"family",smokeIsland.visual.deskItem.family,"children",page.children.map(x=>x.objectName)); Qt.exit(3); return;
                    }
                    console.info("SUMI_APPEARANCE_LAYOUT_OK",JSON.stringify(metrics));
                    desktopRoot.nativeDialogOpen = true;
                    desktopRoot.toggle("appearance", null); desktopRoot.close(); desktopRoot.open("launcher", null); desktopRoot.thursdayToggle(); desktopRoot.codexToggle(null);
                    if (desktopRoot.islandSession.route !== "appearance" || !desktopRoot.nativeDialogOpen || smokeIsland.smokeGrab.active) {
                        console.error("SUMI_NATIVE_DIALOG_HANDOFF_FAILED"); Qt.exit(4); return;
                    }
                    desktopRoot.nativeDialogOpen = false;
                }
                if (name === "pomodoro") {
                    desktopRoot.focusReset(5); desktopRoot.focusStart();
                    if (!desktopRoot.focusRunning || desktopRoot.focusDeadline <= Date.now()) { Qt.exit(5); return; }
                    desktopRoot.focusPause();
                    if (desktopRoot.focusRunning || desktopRoot.focusRemaining <= 0) { Qt.exit(6); return; }
                    desktopRoot.focusReset(25);
                }
            }
            desktopRoot.smokePhase++;
            if (desktopRoot.smokePhase === desktopRoot.smokePanels.length) { desktopRoot.close(); console.info("SUMI_UI_SMOKE_OK"); Qt.quit(); return; }
            desktopRoot.open(desktopRoot.smokePanels[desktopRoot.smokePhase], null);
        }
    }
    TestCase { id: probe; when: false }
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sumi-ui-smoke-') as temporary:
        work = Path(temporary)
        config = work / 'shell'
        shutil.copytree(repo / 'shell', config)
        adapt = runpy.run_path(str(repo / 'tests/qml/run-island-smoke.py'))['adapt']
        path = config / 'DynamicIsland.qml'
        path.write_text(adapt(path.read_text()))
        visual = config / 'components/IslandContent.qml'
        visual.write_text(visual.read_text().replace('HoverHandler {', 'HoverHandler { enabled: false;'))
        source = (config / 'shell.qml').read_text().replace('import QtQuick\n', 'import QtQuick\nimport QtTest\n', 1)
        source = re.sub(r'^import "(?:ThursdayNative|CodexStatusModule)"[^\n]*\n', '', source, flags=re.M)
        source = re.sub(r'^    // Native assistant integration begins\..*?^    // Native assistant integration ends\.\n', '    QtObject { id: codexLoader; readonly property var item: null }\n    QtObject { id: thursdayLoader; readonly property var item: null }\n', source, flags=re.M | re.S)
        source = re.sub(r'^    Variants \{.*\n', '', source, flags=re.M)
        source = re.sub(r'^    DesktopWidgets \{.*\n', '    QtObject { id: widgetSurface }\n    QtObject { id: overlays; property var instances: [] }\n', source, flags=re.M)
        # The probe reads the existing Item through its public host alias.
        content = config / 'components/IslandContent.qml'
        content.write_text(content.read_text().replace('    property bool dashboardReady:', '    readonly property var deskItem: dashboard.item\n    property bool dashboardReady:', 1))
        (config / 'shell.qml').write_text(source[:source.rfind('}')] + PROBE + '}\n')
        runtime = work / 'runtime'; runtime.mkdir(mode=0o700)
        env = dict(os.environ, SUMI_PREVIEW='1', SUMI_STATE_DIR=str(work/'state'), SUMI_DESKTOPCTL=str(repo/'bin/desktopctl'), QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(['qs', '-p', str(config)], env=env, capture_output=True, text=True, timeout=20)
        output = result.stdout + result.stderr
        errors = ('TypeError:', 'ReferenceError:', 'Failed to load configuration', 'Unable to assign [undefined]', 'Binding loop', '_FAILED')
        if result.returncode or 'SUMI_UI_SMOKE_OK' not in output or any(error in output for error in errors):
            raise SystemExit(output)
        for name in ('launcher','files','clipboard','appearance','widgets','settings','calendar','media','notifications','pomodoro','help','power'):
            if f'SUMI_UI_CONTENT {name}' not in output: raise SystemExit(f'{name} did not instantiate\n{output}')
        if 'SUMI_APPEARANCE_LAYOUT_OK' not in output: raise SystemExit(output)
        print('PASS: 11 island entry points and standalone settings route render; active page; native dialog focus guard; focus start/pause/reset; real appearance catalog and bounded gallery/preview')
        print('Native window wrappers replaced only in the temporary fixture; compositor QA remains required')


if __name__ == '__main__': main()
