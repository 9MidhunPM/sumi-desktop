#!/usr/bin/env python3
"""Replay a restored Thursday snapshot through the real shell and adapter."""
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location('bridge_fixture', Path(__file__).with_name('run-island-thursday-bridge-smoke.py'))
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
fixtures = re.sub(r'    QtObject \{\n        id: fakeThursday.*?\n    \}\n', '    ThursdayIntegration.Thursday { id: fakeThursday; repoRoot: "" }\n', bridge.FIXTURES, count=1, flags=re.S)
TEST = '''
    TestCase {
        name: "ThursdayRestart"
        when: true
        function check(value, message) { if (!value) { console.error("THURSDAY_RESTART_FAILED", message); Qt.exit(1); throw new Error(message); } }
        function test_restored_snapshot() {
            desktopRoot.registerIsland(fakeIsland);
            fakeThursday.handle({type:"init",data:{conversation_id:4,model_ready:true,
                history:[{role:"user",content:"Last prompt"},{role:"assistant",content:"Last answer"}],
                voice_state:{session_id:"old-voice",state:"submitted",transcript:"Last prompt"}}});
            wait(30);
            check(!desktopRoot.thursdayOutputActive && desktopRoot.thursdayOutputUntil === 0 && !fakeIsland.pinned,
                "Restored transcript must not reopen Thursday after shell restart");
            check(fakeThursday.messages.count === 2 && fakeThursday.transcript === "Last prompt", "History and transcript remain available");
            fakeThursday.handle({type:"status",data:{busy:false}});
            check(!desktopRoot.thursdayOutputActive, "Idle status cannot present restored text");
            fakeThursday.handle({type:"voice_state",data:{session_id:"old-voice",state:"submitted",transcript:"Last prompt"}});
            check(!desktopRoot.thursdayOutputActive, "An echoed terminal voice state cannot replay the previous prompt");
            desktopRoot.openThursdayFull();
            check(fakeIsland.pinned && fakeIsland.section === "thursday", "Explicit open still shows Thursday");
            fakeIsland.dismiss(false);
            fakeThursday.handle({type:"voice_state",data:{session_id:"new-voice",state:"listening",partial_transcript:"New request"}});
            check(desktopRoot.thursdayOutputActive, "Fresh voice activity still presents");
            fakeThursday.handle({type:"voice_state",data:{session_id:"new-voice",state:"submitted",transcript:"New request"}});
            check(desktopRoot.thursdayOutputUntil > Date.now(), "Fresh terminal transcript retains reading time");
            fakeThursday.handle({type:"init",data:{conversation_id:4,model_ready:true,voice_state:{session_id:"new-voice",state:"submitted",transcript:"New request"}}});
            check(!desktopRoot.thursdayOutputActive && desktopRoot.thursdayOutputUntil === 0, "Reconnect snapshots clear old presentation holds too");
            fakeThursday.handle({type:"final_response",data:{content:"Fresh reply"}});
            check(desktopRoot.thursdayOutputActive, "Fresh server reply still presents");
            fakeThursday.handle({type:"init",data:{conversation_id:4,model_ready:true}});
            check(!fakeThursday.presentationEnabled, "Snapshot resets presentation ownership");
            fakeThursday.send({command:"voice_start"});
            check(fakeThursday.presentationEnabled && fakeThursday.errorText.length > 0,
                "A fresh local voice attempt enables feedback even when sending fails");
            console.info("THURSDAY_RESTART_OK"); Qt.quit();
        }
    }
'''

def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sumi-thursday-restart-') as directory:
        work = Path(directory)
        config = work / 'shell'
        shutil.copytree(repo/'shell', config)
        media = config / 'services/Media.qml'
        media.write_text(media.read_text().replace('readonly property var players: Mp.Mpris.players.values', 'property var players: []'))
        source = (config/'shell.qml').read_text().replace('import QtQuick\n', 'import QtQuick\nimport QtTest\n', 1)
        source = re.sub(r'^    // Native assistant integration begins\..*?^    // Native assistant integration ends\.\n', fixtures, source, flags=re.M|re.S)
        source = re.sub(r'^    Variants \{\n        model: Quickshell\.screens\n        WorkspaceOverview \{.*?^    \}\n', '', source, flags=re.M|re.S)
        source = re.sub(r'^    Variants \{.*\n', '', source, flags=re.M)
        source = re.sub(r'^    DesktopWidgets \{.*\n', '', source, flags=re.M)
        source = source[:source.rfind('}')] + TEST + '}\n'
        (config/'shell.qml').write_text(source)
        runtime=work/'runtime'; runtime.mkdir(mode=0o700)
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen', SUMI_PREVIEW='1', SUMI_STATE_DIR=str(work/'state'), XDG_RUNTIME_DIR=str(runtime))
        result=subprocess.run(['qs','-p',str(config)],env=env,capture_output=True,text=True,timeout=12)
        output=result.stdout+result.stderr
        if result.returncode or 'THURSDAY_RESTART_OK' not in output or any(x in output for x in ['TypeError:', 'ReferenceError:', 'Unable to assign [undefined]', 'Failed to load configuration', 'FAIL!', 'Binding loop']):
            raise SystemExit(output)
        print('PASS: restored Thursday snapshots stay collapsed; history retained; explicit open and fresh voice/replies still work')

if __name__=='__main__': main()
