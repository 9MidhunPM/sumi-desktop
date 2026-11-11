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
    verify(S.SystemStats.consumers[page.statsConsumer] === true, "Overview requests system stats while active")
    page.active = false; wait(20)
    verify(S.SystemStats.consumers[page.statsConsumer] === false, "Overview releases system stats when inactive")
    page.active = true; wait(20)
    page.anchors.fill = null
    for (const width of [320, 419, 519, 520, 640]) {
     page.width = width; page.height = 1100; wait(80)
     const wifi = findChild(page, "islandConnectivityModule")
     const media = findChild(page, "islandControlsMusicModule")
     const brightness = findChild(page, "islandDashboardBrightness")
     const volume = findChild(page, "islandDashboardVolume")
     verify(wifi && media && brightness && volume, "Historical control modules remain available")
     compare(brightness.orientation, Qt.Vertical, "Brightness remains vertical")
     compare(volume.orientation, Qt.Vertical, "Volume remains vertical")
     const wifiPos = wifi.mapToItem(page, 0, 0), mediaPos = media.mapToItem(page, 0, 0)
     const levelPos = brightness.mapToItem(page, 0, 0)
     verify(wifiPos.x >= 0 && mediaPos.x + media.width <= page.width + 1, "Top tiles fit the page")
     verify(Math.abs(wifiPos.y - mediaPos.y) < 1 && wifiPos.x + wifi.width <= mediaPos.x + 1, "Connectivity and media share a row")
     if (width < 520) verify(levelPos.y >= wifiPos.y + wifi.height, "Compact sliders occupy the next row")
     else verify(Math.abs(levelPos.y - wifiPos.y) < 1, "Wide sliders share the top row")
     for (const metric of ["cpu", "memory", "storage"]) verify(findChild(page, "islandUsageValue-" + metric), "Usage indicator remains available: " + metric)
     verify(findChild(page, "islandPowerProfile-performance"), "Power profiles remain available")
    }
    page.width = 640; page.height = 530; wait(80)
    const connectivity = findChild(page, "islandConnectivityModule")
    verify(connectivity !== null, "Original control modules retained")
    verify(findChild(connectivity.parent, "islandUsageValue-cpu"), "Usage remains in the original overview")
    verify(findChild(page, "islandQuickThursday") === null, "Original Controls omit unrelated shortcut blocks")
    const brightness = findChild(page, "islandDashboardBrightness")
    const volume = findChild(page, "islandDashboardVolume")
    compare(brightness.orientation, Qt.Vertical, "Brightness uses the vertical reference control")
    compare(volume.orientation, Qt.Vertical, "Volume shares the vertical control grammar")
    page.spectrumSamples = [25, 75, 40, 90]
    wait(20)
    compare(findChild(page, "islandControlsWaveform").samples[1], 75, "Real spectrum samples reach the Controls mini player")
    verify(findChild(page, "islandTool-launcher") === null, "Original Controls omit the tool grid")
    verify(findChild(page, "islandQuickNotification") === null, "Notifications remain in their own route")
    page.route = "wifi"; wait(40)
    verify(S.SystemStats.consumers[page.statsConsumer] === false, "Device pages release system stats demand")
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
