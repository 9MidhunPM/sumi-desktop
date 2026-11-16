#!/usr/bin/env python3
"""Exercise actual Hyprland action construction with an inert dispatcher."""
import os
from pathlib import Path
import subprocess
import tempfile

repo = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='sumi-hypr-actions-') as temporary:
    work = Path(temporary)
    (work / 'runtime').mkdir(mode=0o700)
    services = work / 'services'
    services.mkdir()
    source = (repo / 'shell/services/HyprlandActions.qml').read_text()
    source = source.replace('Singleton {', '''Singleton {
    property bool testPreview: false
    property bool testLua: true
    property var dispatched: []
    function testDispatch(command) { dispatched = dispatched.concat([command]); }
''', 1)
    source = source.replace('Desktop.preview', 'testPreview').replace('Hyprland.usingLua', 'testLua').replace('Hyprland.dispatch(', 'testDispatch(')
    (services / 'HyprlandActions.qml').write_text(source)
    (services / 'qmldir').write_text('singleton HyprlandActions HyprlandActions.qml\n')
    (work / 'probe.qml').write_text('''import QtQuick
import Quickshell
import "services" as S
ShellRoot {
 Component.onCompleted: Qt.callLater(() => {
  const a = S.HyprlandActions;
  a.moveWindowToWorkspace("0xabc", "special:magic");
  if (a.dispatched.length !== 1 || a.dispatched[0] !== 'hl.dsp.window.move({ window = "address:0xabc", workspace = "special:magic", follow = false })') { console.error("BAD_LUA", JSON.stringify(a.dispatched)); Qt.exit(1); return; }
  a.testLua = false;
  a.moveWindowToWorkspace("0x12AB", 5);
  if (a.dispatched.length !== 2 || a.dispatched[1] !== 'movetoworkspacesilent 5,address:0x12AB') { console.error("BAD_LEGACY", JSON.stringify(a.dispatched)); Qt.exit(1); return; }
  a.moveWindowToWorkspace("abc", "2");
  a.focusWindow("abc");
  if (a.dispatched[2] !== 'movetoworkspacesilent 2,address:0xabc' || a.dispatched[3] !== 'focuswindow address:0xabc') { console.error("BAD_RAW_ADDRESS", JSON.stringify(a.dispatched)); Qt.exit(1); return; }
  a.testLua = true;
  a.focusWindow("0X12AB");
  if (a.dispatched[4] !== 'hl.dsp.focus({ window = "address:0x12AB" })') { console.error("BAD_FOCUS_LUA", JSON.stringify(a.dispatched)); Qt.exit(1); return; }
  a.moveWindowToWorkspace("abc", "10");
  a.moveWindowToWorkspace("abc", "name:workroom");
  if (a.dispatched.length !== 7 || !a.dispatched[5].includes('workspace = "10"') || !a.dispatched[6].includes('workspace = "name:workroom"')) { console.error("BAD_VALID_WORKSPACE", JSON.stringify(a.dispatched)); Qt.exit(1); return; }
  a.moveWindowToWorkspace("invalid", "1");
  a.focusWindow("invalid");
  a.moveWindowToWorkspace("0x123", "");
  a.moveWindowToWorkspace("0x123", "1,address:evil");
  a.moveWindowToWorkspace("0x123", "1" + String.fromCharCode(13));
  a.moveWindowToWorkspace("0x123", "1" + String.fromCharCode(10));
  a.moveWindowToWorkspace("0x123", "1" + String.fromCharCode(0));
  a.testPreview = true; a.moveWindowToWorkspace("0x123", "1");
  if (a.dispatched.length !== 7) { console.error("BAD_GUARD", JSON.stringify(a.dispatched)); Qt.exit(1); return; }
  console.log("ACTIONS_PASS"); Qt.exit(0);
 })
 Timer { interval: 5000; running: true; onTriggered: Qt.exit(2) }
}''')
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', XDG_RUNTIME_DIR=str(work / 'runtime'))
    result = subprocess.run(['qs', '-p', str(work / 'probe.qml')], env=env, text=True, capture_output=True, timeout=10)
    output = result.stdout + result.stderr
    if result.returncode or 'ACTIONS_PASS' not in output:
        print(output)
        raise SystemExit(result.returncode or 1)
    print('PASS: silent Lua and legacy window moves; invalid selectors and preview isolation')
