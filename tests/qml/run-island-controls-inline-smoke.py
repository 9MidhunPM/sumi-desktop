#!/usr/bin/env python3
"""Exercise embedded controls routing and local form cancellation without devices."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "components"
import "services" as S
ShellRoot {
 QtObject {
  id: fake
  property var islandSession: ({entityId: ""})
  property string panel: ""
  property string settingsSection: ""
  property var activeScreen: null
  property bool focusRunning: false
  property double focusRemaining: 1500000
  property double focusDeadline: 0
  function close() {}
  function open(name, screen) {}
  function focusStart() {}
  function focusPause() {}
  function focusReset(minutes) {}
 }
 Timer { interval: 4000; running: true; onTriggered: Qt.exit(2) }
 FloatingWindow {
  visible: true; implicitWidth: 640; implicitHeight: 530
  IslandControlsPage {id: page; anchors.fill: parent; app: fake; active: true; onRouteRequested: route => page.route = route}
  TestCase {
   when: true
   function test_inline() {
    wait(100)
    page.anchors.fill = null
    for (const width of [344, 419, 420, 640]) {
     page.width = width; page.height = 1000; wait(80)
     const grid = findChild(page, "islandControlModules")
     const wifi = findChild(page, "islandConnectivityModule")
     const dnd = findChild(page, "islandDndTile")
     const night = findChild(page, "islandNightTile")
     verify(dnd.width >= 40 && night.width >= 40, "Tiles remain usable")
     const dndPos = dnd.mapToItem(grid, 0, 0)
     const nightPos = night.mapToItem(grid, 0, 0)
     verify(dndPos.x + dnd.width <= grid.width + 1, "DND stays within grid")
     verify(nightPos.x + night.width <= grid.width + 1, "Night light stays within grid")
     if (width < 420) verify(dndPos.y >= wifi.y + wifi.height, "Compact controls stack")
     else { compare(Math.round(dndPos.y), Math.round(wifi.y), "Wide controls align"); compare(Math.round(dnd.width * 2 + 12), Math.round(wifi.width), "Wide columns balanced") }
     const title = findChild(dnd, "tileTitle")
     const status = findChild(dnd, "tileStatus")
     verify(title.y + title.height <= status.y + 1, "Title and status do not overlap")
    }
    page.width = 640; page.height = 530; wait(80)
    const connectivity = findChild(page, "islandConnectivityModule")
    verify(connectivity !== null, "Original control modules retained")
    compare(findChild(connectivity.parent, "islandUsageValue-cpu"), null, "Usage does not crowd the overview")
    verify(findChild(page, "islandQuickThursday") !== null, "Assistant remains immediately reachable")
    const brightness = findChild(page, "islandDashboardBrightness")
    const volume = findChild(page, "islandDashboardVolume")
    compare(brightness.orientation, Qt.Horizontal, "Brightness uses the horizontal reference control")
    compare(volume.orientation, Qt.Horizontal, "Volume shares the horizontal control grammar")
    page.spectrumSamples = [25, 75, 40, 90]
    wait(20)
    compare(findChild(page, "islandControlsWaveform").samples[1], 75, "Real spectrum samples reach the Controls mini player")
    for (const route of ["calendar", "files", "launcher", "widgets"]) {
     findChild(page, "islandTool-" + route).clicked()
     compare(page.route, route, "Quick tool retains its original route: " + route)
     page.route = "controls"
    }
    S.Notifications.history = [1,2,3].map(id => ({id:id, appName:"Fixture", summary:"Notice " + id, body:"Content", time:new Date(), actions:[]}))
    wait(30)
    function matches(item) { let total = item.objectName === "islandQuickNotification" ? 1 : 0; for (const child of item.children || []) total += matches(child); return total; }
    compare(matches(page), 2, "Only two recent notifications shown")
    const notification = findChild(page, "islandQuickNotification")
    notification.openRequested()
    compare(page.route, "notification", "Notification opens inline")
    compare(String(fake.islandSession.entityId), String(notification.entry.id), "Selected notification identity retained")
    page.route = "controls"
    page.route = "wifi"; wait(40)
    const body = findChild(page, "settingsBody")
    verify(body.visible)
    verify(!findChild(page, "settingsClose").visible, "Host owns close")
    verify(!findChild(page, "settingsBack").visible, "Host owns Back")
    const settings = body.parent.parent
    settings.selectedNetwork = {name: "Fixture"}
    verify(page.back(), "Back cancels Wi-Fi form first")
    compare(settings.selectedNetwork, null)
    verify(!page.back(), "Host receives second Back")
    page.route = "audio"; wait(40)
    verify(!findChild(page,"settingsAudioManager").visible, "Sound remains inline")
    page.anchors.fill = null; page.width = 640; page.height = 220; wait(60)
    body.contentItem.contentY = 55
    page.active = false; wait(30)
    page.active = true; wait(60)
    compare(Math.round(body.contentItem.contentY), 55, "Device page scroll survives dismissal")
    page.route = "capture"; wait(40)
    page.route = "audio"; wait(60)
    compare(Math.round(body.contentItem.contentY), 55, "Each device section resumes its scroll")
    page.route = "power"; wait(40)
    const power = findChild(page,"dashboardBody").parent.parent
    power.pendingPower = "shutdown"
    page.active = false; wait(40)
    compare(power.pendingPower, "", "Leaving clears power confirmation")
    console.log("ISLAND_CONTROLS_INLINE_PASS")
    Qt.quit()
   }
  }
 }
}
'''
repo = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="sumi-inline-controls-") as work:
    root = Path(work)
    shutil.copytree(repo / "shell", root / "shell")
    (root / "shell/controls-test.qml").write_text(HARNESS)
    (root / "runtime").mkdir(mode=0o700)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", SUMI_PREVIEW="1", XDG_RUNTIME_DIR=str(root / "runtime"), SUMI_STATE_DIR=str(root / "state"))
    result = subprocess.run(["qs", "-p", str(root / "shell/controls-test.qml")], env=env, capture_output=True, text=True, timeout=15)
    output = result.stdout + result.stderr
    if result.returncode or "ISLAND_CONTROLS_INLINE_PASS" not in output:
        raise SystemExit(output)
    print("PASS: original controls, inline devices, form Back, power confirmation cancellation")
