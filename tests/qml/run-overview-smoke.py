#!/usr/bin/env python3
"""Exercise overview workspace ordering and animation lifecycle with synthetic data."""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='sumi-overview-') as temporary:
    work = Path(temporary)
    shutil.copytree(repo / 'shell', work / 'shell')
    (work / 'runtime').mkdir(mode=0o700)
    component = work / 'shell' / 'WorkspaceOverview.qml'
    source = component.read_text()
    source = source.replace('PanelWindow {', 'Window {', 1)
    source = re.sub(r'^    (screen:|anchors \{|exclusiveZone:|exclusionMode:|WlrLayershell\.).*\n', '', source, flags=re.M)
    source = source.replace('    color: \"transparent\"', '    width: 1200; height: 800\n    color: \"transparent\"')
    source = source.replace('property var entries: []', '''property var fixtureWorkspaces: []
    property var fixtureMoves: []
    function fixtureCenter(index) { const t = workspaceRepeater.itemAt(index); return t.mapToItem(contentItem, t.width / 2, (t.height - 37) / 2); }
    function fixtureDropAt(index) { const tile = workspaceRepeater.itemAt(index); const pt = tile.mapToItem(null, tile.width / 2, (tile.height - 37) / 2); updateDrop(null, pt.x, pt.y); }
    property var entries: []''')
    source = source.replace('S.HyprlandActions.moveWindowToWorkspace(address, target.target)', 'root.fixtureMoves = root.fixtureMoves.concat([{address: address, target: target.target}])')
    source = source.replace('Hyprland.workspaces.values.filter(w => !!w)', 'root.fixtureWorkspaces.filter(w => !!w)')
    source = source.replace('Hyprland.refreshToplevels();', '')
    component.write_text(source)
    (work / 'shell' / 'probe.qml').write_text('''import QtQuick
import QtTest
import Quickshell
ShellRoot {
 TestCase { id: mouseTest; name: 'PointerProbe'; when: false; function click(item, p, button) { mouseClick(item, p.x, p.y, button); } }
 WorkspaceOverview { id: overview; modelData: Quickshell.screens[0]; app: null
  fixtureWorkspaces: [
   {id: 4, name: "4", monitor: {name: "DP-1"}, toplevels: {values: [{title: "one", address: "0xabc"}]}},
   {id: -98, name: "special:magic", monitor: {name: "eDP-1"}, toplevels: {values: []}},
   {id: 1, name: "1", monitor: {name: "eDP-1"}, toplevels: {values: []}}
  ]
  property int closedCount: 0
  property var requested: []
  property var windowRequests: []
  onWorkspaceRequested: target => requested = requested.concat([target])
  onWindowRequested: (target, address) => windowRequests = windowRequests.concat([{target: target, address: address}])
  onOverviewHidden: closedCount++
 }
 Timer { interval: 100; running: true; repeat: true; property int step: 0
  onTriggered: {
   if (step === 0) { overview.opened = true; overview.refreshEntries(); }
   if (step === 1) {
    const a = overview.entries;
    if (a.length !== 4 || a[0].id !== 1 || a[1].id !== 2 || !a[1].empty || a[2].id !== 4 || a[2].windows.length !== 1 || a[3].target !== "special:magic") { console.error("OVERVIEW_MODEL_FAILED", JSON.stringify(a)); Qt.exit(1); return; }
    overview.opened = false;
   }
   if (step === 2) overview.opened = true;
   if (step === 5) {
    if (overview.closedCount !== 0) { console.error("OVERVIEW_STALE_CLOSE"); Qt.exit(1); return; }
    overview.fixtureMoves = [];
    overview.fixtureDropAt(2);
    if (overview.dropIndex !== 2) { console.error("OVERVIEW_DROP_MAP_FAILED", overview.dropIndex); Qt.exit(1); return; }
    overview.finishDrop("0xabc", "1");
    if (overview.fixtureMoves.length !== 1 || overview.fixtureMoves[0].target !== "4" || overview.fixtureMoves[0].address !== "0xabc" || overview.dropIndex !== -1) { console.error("OVERVIEW_MOVE_FAILED"); Qt.exit(1); return; }
    overview.finishDrop("0xabc", "1");
    overview.fixtureDropAt(0); overview.finishDrop("0xabc", "1");
    if (overview.fixtureMoves.length !== 1) { console.error("OVERVIEW_CANCEL_FAILED"); Qt.exit(1); return; }
    overview.selection = 0;
    let event = {angleDelta: {x: 0, y: 120}, pixelDelta: {x: 0, y: 0}, accepted: false};
    overview.navigateScroll(event, false);
    if (overview.selection !== 0 || !event.accepted) { console.error("OVERVIEW_SCROLL_THRESHOLD_FAILED"); Qt.exit(1); return; }
    overview.navigateScroll(event, false);
    if (overview.selection !== 3) { console.error("OVERVIEW_SCROLL_VERTICAL_FAILED", overview.selection); Qt.exit(1); return; }
    overview.selection = 0;
    event = {angleDelta: {x: 0, y: 0}, pixelDelta: {x: 120, y: 0}, accepted: false};
    overview.navigateScroll(event, true);
    if (overview.selection !== 1 || !event.accepted) { console.error("OVERVIEW_SCROLL_HORIZONTAL_FAILED", overview.selection); Qt.exit(1); return; }
    overview.selection = 1;
    event = {angleDelta: {x: 120, y: 0}, pixelDelta: {x: 0, y: 0}, accepted: false};
    overview.navigateScroll(event, true);
    event.angleDelta.x = -240;
    overview.navigateScroll(event, true);
    if (overview.selection !== 0) { console.error("OVERVIEW_REVERSAL_FAILED", overview.selection); Qt.exit(1); return; }
    overview.selection = 1;
    event = {angleDelta: {x: 0, y: 240}, pixelDelta: {x: 0, y: 0}, accepted: false};
    overview.navigateScroll(event, false);
    if (overview.selection !== 1) { console.error("OVERVIEW_MISSING_BELOW_FAILED"); Qt.exit(1); return; }
    overview.selection = 2;
    event = {angleDelta: {x: 240, y: 0}, pixelDelta: {x: 0, y: 0}, accepted: false};
    overview.navigateScroll(event, true);
    if (overview.selection !== 2) { console.error("OVERVIEW_ROW_WRAP_FAILED"); Qt.exit(1); return; }
    overview.selection = 0; overview.horizontalScroll = 0;
    event = {angleDelta: {x: 0, y: 0}, pixelDelta: {x: 250, y: 0}, accepted: false};
    overview.navigateScroll(event, true);
    if (overview.selection !== 2 || Math.abs(overview.horizontalScroll - 70) > 0.01) { console.error("OVERVIEW_SCROLL_REMAINDER_FAILED", overview.selection, overview.horizontalScroll); Qt.exit(1); return; }
    event.pixelDelta.x = -90; overview.navigateScroll(event, true);
    if (overview.selection !== 1) { console.error("OVERVIEW_PIXEL_REVERSAL_FAILED", overview.selection); Qt.exit(1); return; }
    let point = overview.fixtureCenter(2);
    mouseTest.click(overview.contentItem, point, Qt.RightButton);
    // A two-finger (right) click opens the workspace selected by scrolling, not the one under the pointer.
    if (overview.requested.length !== 1 || overview.requested[0] !== "2") { console.error("OVERVIEW_WINDOW_RIGHT_CLICK_FAILED", JSON.stringify(overview.requested)); Qt.exit(1); return; }
    if (overview.windowRequests.length !== 0) { console.error("OVERVIEW_RIGHT_FOCUSED_WINDOW"); Qt.exit(1); return; }
    overview.requested = [];
    mouseTest.click(overview.contentItem, point, Qt.LeftButton);
    if (overview.windowRequests.length !== 1 || overview.windowRequests[0].target !== "4" || overview.windowRequests[0].address !== "0xabc" || overview.requested.length !== 0) { console.error("OVERVIEW_WINDOW_LEFT_CLICK_FAILED", JSON.stringify(overview.windowRequests)); Qt.exit(1); return; }
    point = overview.fixtureCenter(1);
    mouseTest.click(overview.contentItem, point, Qt.RightButton);
    if (overview.requested.length !== 1 || overview.requested[0] !== "4") { console.error("OVERVIEW_EMPTY_RIGHT_CLICK_FAILED", JSON.stringify(overview.requested)); Qt.exit(1); return; }
    overview.requested = [];
    overview.openWorkspace(2);
    if (overview.selection !== 2 || overview.requested.length !== 1 || overview.requested[0] !== "4") { console.error("OVERVIEW_OPEN_WORKSPACE_FAILED"); Qt.exit(1); return; }
    overview.opened = false;
    overview.openWorkspace(0);
    if (overview.requested.length !== 1) { console.error("OVERVIEW_OPEN_WHILE_CLOSED"); Qt.exit(1); return; }
   }
   if (step === 9) { if (overview.closedCount !== 1 || overview.visible) { console.error("OVERVIEW_CLOSE_FAILED", overview.closedCount, overview.visible); Qt.exit(1); return; } console.log("OVERVIEW_PASS"); Qt.exit(0); }
   step++;
  }
 }
 Timer { interval: 5000; running: true; onTriggered: Qt.exit(2) }
}''')
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', SUMI_PREVIEW='1', XDG_RUNTIME_DIR=str(work / 'runtime'), SUMI_STATE_DIR=str(work / 'state'))
    result = subprocess.run(['qs', '-p', str(work / 'shell' / 'probe.qml')], env=env, text=True, capture_output=True, timeout=10)
    output = result.stdout + result.stderr
    if result.returncode or 'OVERVIEW_PASS' not in output or 'TypeError:' in output or 'Binding loop detected' in output:
        print(output)
        raise SystemExit(result.returncode or 1)
    print('PASS: workspace model; actual right and left mouse clicks; drag destination and cancellation; 2D scroll remainder, reversal and boundaries; interrupted close lifecycle')
