#!/usr/bin/env python3
"""Navigation history uses real session state, with no native mutations."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HARNESS = '''import QtQuick
import Quickshell
import "services" as S
ShellRoot {
 S.IslandSession { id: session }
 function check(value, message) { if (!value) { console.error("SESSION_FAILED",message); Qt.exit(1); throw new Error(message); } }
 Timer { interval: 1; running: true; onTriggered: {
  check(session.route === "controls", "Single useful root instead of Home landing");
  session.navigate("media"); session.navigate("audio");
  check(session.back() && session.route === "media", "Sound Back returns to originating music page");
  session.navigate("appearance"); session.navigate("widgets");
  check(session.back() && session.route === "appearance", "Cross-family detail retains origin");
  session.navigate("notification", 14);
  check(session.entityId === "14", "Entity IDs normalized");
  check(session.back() && session.route === "appearance", "Notification back returns to caller");
  session.navigate("home"); check(session.route === "controls" && !session.back(), "Legacy Home opens unified surface");
  session.navigate("desktop"); check(session.route === "launcher", "Desktop alias opens useful Search");
  session.navigate("files", "", "fresh"); check(session.back() && session.route === "controls", "Fresh shortcut has main surface as return");
  const before=session.revision; check(!session.navigate("bogus") && before===session.revision, "Unknown route cannot change state");
  console.log("ISLAND_SESSION_OK"); Qt.quit();
 }}
}'''

def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sumi-session-') as tmp:
        work = Path(tmp)
        shutil.copytree(repo/'shell/services', work/'services')
        (work/'shell.qml').write_text(HARNESS)
        (work/'runtime').mkdir(mode=0o700)
        env = dict(os.environ, SUMI_PREVIEW='1', QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(work/'runtime'))
        result = subprocess.run(['qs','-p',str(work)], env=env, capture_output=True, text=True, timeout=15)
        output = result.stdout+result.stderr
        if result.returncode or 'ISLAND_SESSION_OK' not in output:
            raise SystemExit(output)
        print('PASS: unified root, real route history, caller return, aliases, entities and invalid routes')

if __name__ == '__main__': main()
