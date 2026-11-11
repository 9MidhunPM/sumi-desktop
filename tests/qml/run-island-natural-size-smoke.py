#!/usr/bin/env python3
"""Natural page metrics must not feed back from the animated viewport height."""
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
 S.IslandSession { id: session }
 QtObject { id: fakeApp
  property var islandSession: session
  property var activeScreen: null
  property var codexStatus: null
  property bool nativeDialogOpen: false
  property bool focusRunning: false
  property double focusDeadline: 0
  property double focusRemaining: 1500000
  function open(name, screen) { return true; }
  function close() {}
  function focusReset(minutes) {} function focusStart() {} function focusPause() {}
 }
 FloatingWindow { visible: true; implicitWidth: 680; implicitHeight: 600
  IslandCorePage { id: core; app: fakeApp; route: "calendar"; width: 440; height: 500; visible: false }
  IslandControlsPage { id: controls; app: fakeApp; route: "pomodoro"; width: 380; height: 500; visible: false }
  IslandDesktopPage { id: desktop; app: fakeApp; route: "launcher"; width: 560; height: 500 }
  TestCase { name: "IslandNaturalMeasurements"; when: true
   function check(value, message) { if (!value) { console.error("NATURAL_SIZE_FAILED",message); Qt.exit(1); throw new Error(message); } }
   function test_sizes() {
    wait(300);
    for (const page of [core, controls, desktop]) {
     const natural = page.contentHeight;
     check(isFinite(natural) && natural > 0, "Natural metric is usable: " + page.route);
     page.height = 220; wait(50);
     check(Math.abs(page.contentHeight - natural) < .5, "Height independent of viewport: " + page.route + " " + natural + " " + page.contentHeight);
    }
    const launcher = findChild(desktop,"islandDesktopLauncherLoader").item;
    const search = findChild(launcher,"launcherSearch");
    launcher.tab = "Actions"; search.text = ""; wait(80);
    const full = desktop.contentHeight;
    search.text = "there-can-be-no-action-matching-this-fixture"; wait(80);
    check(launcher.entries.length === 0 && desktop.contentHeight < full - 200, "Search shrinks when no result needs a list");
    core.route = "notification"; wait(80);
    check(core.contentHeight > 0 && core.contentHeight < 300, "Missing notification has compact natural layout");
    console.info("ISLAND_NATURAL_SIZE_OK"); Qt.quit();
   }
  }
 }
}'''

def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sumi-natural-size-') as temporary:
        work = Path(temporary)
        shutil.copytree(repo/'shell', work/'shell')
        (work/'shell/shell.qml').write_text(HARNESS)
        (work/'runtime').mkdir(mode=0o700)
        env = dict(os.environ, SUMI_PREVIEW='1', QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(work/'runtime'), SUMI_STATE_DIR=str(work/'state'))
        result = subprocess.run(['qs','-p',str(work/'shell')],env=env,capture_output=True,text=True,timeout=20)
        output = result.stdout+result.stderr
        if result.returncode or 'ISLAND_NATURAL_SIZE_OK' not in output or any(error in output for error in ('Binding loop','ReferenceError:','TypeError:','Unable to assign [undefined]')):
            raise SystemExit(output)
        print('PASS: natural calendar/focus/search measurements independent of viewport; result-aware search shrinking; compact missing notification')

if __name__ == '__main__': main()
