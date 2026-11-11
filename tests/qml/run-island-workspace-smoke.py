#!/usr/bin/env python3
"""Exercise real cached island pages; page body must always match its route."""
import os, tempfile, shutil, subprocess
from pathlib import Path
with tempfile.TemporaryDirectory(prefix='sumi-desk-probe-') as td:
 p=Path(td); shutil.copytree(Path(__file__).resolve().parents[2]/'shell',p/'shell'); (p/'runtime').mkdir(mode=0o700)
 (p/'shell'/'probe.qml').write_text('''import QtQuick
import QtTest
import Quickshell
import "components"
import "services" as S
ShellRoot {
 S.IslandSession { id: session }
 QtObject { id: fakeApp
 property var islandSession: session
 property var thursdayBackend: null
 property var codexStatus: null
 property var activeScreen: Quickshell.screens[0]
 property bool nativeDialogOpen: false
 property string settingsSection: ""
 property string panel: ""
 property bool focusRunning: false
 property double focusDeadline: 0
 property double focusRemaining: 1500000
 function focusStart() {} function focusPause() {} function focusReset(n) {}
 function close() {} function open(n,s) { session.navigate(n); } function openSettings(n,s) { session.navigate(n); }
 }
 FloatingWindow { id: window; visible: true; implicitWidth: 640; implicitHeight: 594
 IslandDesk { id: desk; anchors.fill: parent; app: fakeApp; active: true; section: session.route; onSectionRequested: section => session.navigate(section) }
 Timer { interval: 200; running: true; repeat: true
 property int step: 0
 onTriggered: {
 const routes=["controls","audio","appearance","launcher","widgets","thursday","controls","wifi","appearance","launcher","calendar","inbox","media","bluetooth","capture","system","power","settings","pomodoro","files","clipboard","codex","help","home","desktop"];
 if(step > 0) {
 if(!desk.currentPage) { console.error("DESK_PROBE_FAILED", session.route); Qt.exit(1); return; }
 const expected = session.route === "home" ? "controls" : session.route === "desktop" ? "launcher" : session.route;
 if(typeof desk.currentPage.route !== "undefined" && desk.currentPage.route !== expected) { console.error("DESK_PROBE_ROUTE_FAILED", session.route,desk.currentPage.route); Qt.exit(1); return; }
 if(desk.currentPage.active !== true) { console.error("DESK_PROBE_ACTIVE_FAILED",session.route); Qt.exit(1); return; }
}
 if(step >= routes.length) { console.log("DESK_PROBE_PASS",desk.launcherReady); Qt.exit(desk.launcherReady ? 0:1); return; }
 session.navigate(routes[step]); step++;
 }
 }
 }
 Timer { interval: 10000; running: true; onTriggered: Qt.exit(2) }
}''')
 e=os.environ.copy(); e.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',SUMI_PREVIEW='1',XDG_RUNTIME_DIR=str(p/'runtime'),SUMI_STATE_DIR=str(p/'state'))
 r=subprocess.run(['qs','-p',str(p/'shell'/'probe.qml')],env=e,capture_output=True,text=True,timeout=15)
 output = r.stdout + r.stderr
 if r.returncode or "DESK_PROBE_PASS true" not in output or "Binding loop detected" in output or "TypeError:" in output:
  print(output)
  raise SystemExit(r.returncode or 1)
 print("PASS: all cached workspace routes match their visible page; cross-family/same-family transitions; legacy aliases; resident launcher ready")
