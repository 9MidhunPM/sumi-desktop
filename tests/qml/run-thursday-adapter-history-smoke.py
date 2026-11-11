#!/usr/bin/env python3
"""Test Sumi-owned Thursday adapter with inert ordered native-client events."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "integrations"
import "components"
ShellRoot {
 Thursday { id: backend; repoRoot: "" }
 FloatingWindow { visible: true; implicitWidth: 560; implicitHeight: 620
 IslandThursdayPage { id: firstPage; anchors.fill: parent; backend: backend; active: true }
 IslandThursdayPage { id: secondPage; anchors.fill: parent; backend: backend; active: false; visible: false }
 TestCase {
  name: "ThursdayAdapterHistory"
  when: true
  function check(value, message) { if (!value) { console.error("ADAPTER_FAILED", message); Qt.exit(1); throw new Error(message); } }
  function eq(a,b) { check(a === b, String(a) + " expected " + String(b)); }
  function test_protocol() {
   wait(40);
   const firstComposer = findChild(firstPage,"islandThursdayComposer");
   const secondComposer = findChild(secondPage,"islandThursdayComposer");
   firstComposer.text = "  Draft across monitors  ";
   eq(backend.composerDraft,"  Draft across monitors  ");
   eq(secondComposer.text,firstComposer.text);
   firstPage.active=false; secondPage.active=true;
   eq(secondComposer.text,"  Draft across monitors  ");
   secondComposer.text="Edited on another monitor";
   eq(firstComposer.text,"Edited on another monitor");
   backend.submittedComposerDraft=backend.composerDraft; backend.submittedComposerPrompt=backend.composerDraft.trim();
   backend.handle({type:"native_command_result",data:{command:"message"}});
   eq(backend.composerDraft,"Edited on another monitor");
   backend.handle({type:"user_message",data:{content:"Remote unrelated message"}});
   eq(backend.composerDraft,"Edited on another monitor");
   backend.handle({type:"user_message",data:{content:"Edited on another monitor"}});
   eq(backend.composerDraft,""); eq(firstComposer.text,""); eq(secondComposer.text,"");
   secondComposer.text="Newer draft";
   backend.submittedComposerDraft="Old draft"; backend.submittedComposerPrompt="Old draft";
   backend.handle({type:"user_message",data:{content:"Old draft"}});
   eq(backend.composerDraft,"Newer draft"); eq(secondComposer.text,"Newer draft");
   firstPage.active=true; secondPage.active=false;
   backend.handle({type:"init", data:{conversation_id:4, history:[{role:"user",content:"Earlier"},{role:"assistant",content:"Previous response"}],model_ready:true}});
   wait(60);
   eq(backend.messages.count,2); eq(backend.knownConversations[0],4);
   backend.handle({type:"user_message",data:{conversation_id:4,content:"Next"}});
   backend.handle({type:"token",data:{chunk:"Hello "}});
   backend.handle({type:"token",data:{chunk:"there"}});
   eq(backend.messages.count,4); eq(backend.messages.get(3).body,"Hello there");
   backend.handle({type:"final_response",data:{content:"Hello there."}});
   eq(backend.messages.count,4); eq(backend.messages.get(3).body,"Hello there.");
   backend.historyRequest=10;
   backend.handle({type:"native_conversation",data:{conversation_id:4,request_id:9,messages:[]}});
   eq(backend.messages.count,4);
   backend.handle({type:"native_conversation",data:{conversation_id:7,request_id:10,messages:[]}});
   eq(backend.messages.count,4);
   backend.handle({type:"native_conversation",data:{conversation_id:4,request_id:10,messages:[{role:"assistant",content:"Snapshot"}]}});
   eq(backend.messages.count,1);
   backend.handle({type:"voice_state",data:{state:"listening",session_id:"voice-a",level:0.61,partial_transcript:"Hello"}});
   eq(backend.visualizerLevel,0.61); eq(backend.transcript,"Hello");
   backend.handle({type:"voice_state",data:{state:"submitted",session_id:"voice-a",partial_transcript:"Hello",transcript:"Hello there",task_id:"task-a",conversation_id:4}});
   eq(backend.partialTranscript,"Hello"); eq(backend.finalTranscript,"Hello there"); eq(backend.transcript,"Hello there"); eq(backend.voiceTaskId,"task-a");
   backend.handle({type:"voice_state",data:{state:"listening",session_id:"voice-b",partial_transcript:"New"}});
   eq(backend.transcript,"New"); eq(backend.finalTranscript,"");
   backend.handle({type:"voice_state",data:{state:"submitted",session_id:"voice-a",transcript:"Late"}});
   eq(backend.voiceSession,"voice-b"); eq(backend.transcript,"New");
   backend.handle({type:"voice_state",data:{state:"idle"}});
   backend.handle({type:"native_output",data:{known:true,audible:true}});
   backend.handle({type:"native_playback",data:{generation_id:"pcm-a",state:"playing",level:0.7,position_ms:500}});
   check(backend.nativePlayback && backend.speaking,"Native PCM owns playback"); eq(backend.visualizerLevel,0.7);
   eq(backend.nativePlaybackState,"playing"); eq(backend.nativePlaybackGeneration,"pcm-a");
   backend.handle({type:"native_playback",data:{generation_id:"pcm-a",state:"idle",position_ms:6500,underruns:0,underrun_ms:0,prebuffer_ms:201}});
   eq(backend.nativePlaybackState,"idle"); check(!backend.nativePlayback,"PCM ends once");
   eq(backend.nativePlaybackMetrics.position_ms,6500); eq(backend.nativePlaybackMetrics.prebuffer_ms,201);
   backend.handle({type:"tts_status",data:{client_id:"native",generation_id:"pcm-a",state:"fallback",message:"Online voice is unavailable. Using local speech."}});
   check(backend.speechError.indexOf("Using local speech")>=0,"Fallback must be visible");
   backend.handle({type:"tts_status",data:{client_id:"native",generation_id:"pcm-a",state:"ready"}});
   eq(backend.speechError,"");
   backend.handle({type:"tts_status",data:{client_id:"native",generation_id:"pcm-a",state:"unavailable",message:"Emma is unavailable."}});
   check(backend.speechError.length>0,"Current failure is visible");
   backend.handle({type:"tts_preparing",data:{generation_id:"pcm-a"}});
   eq(backend.speechError,"");
   backend.stopAudio();
   backend.handle({type:"native_playback",data:{generation_id:"pcm-a",state:"playing",level:1}});
   check(!backend.nativePlayback,"Retired PCM cannot restart");
   backend.handle({type:"voice_options",data:{engine:"online",voice:"Emma",speed:1,engines:[{id:"online",label:"Online",available:true,voices:[{id:"Emma",label:"Emma"}]}]}});
   eq(backend.availableVoices.length,1);
   backend.submittedDraft="Keep draft";
   backend.handle({type:"user_message",data:{conversation_id:4,content:"Keep draft"}});
   eq(backend.submittedDraft,"Keep draft");
   backend.handle({type:"native_command_result",data:{command:"message"}});
   eq(backend.submittedDraft,"");
   console.info("THURSDAY_ADAPTER_HISTORY_OK"); Qt.quit();
  }
 }
}
}
'''

def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-thursday-adapter-") as directory:
        work = Path(directory)
        shutil.copytree(repo / "shell", work / "shell")
        (work / "shell/shell.qml").write_text(HARNESS)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        env = dict(os.environ, SUMI_PREVIEW="1", QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(["qs", "-p", str(work / "shell")], env=env, capture_output=True, text=True, timeout=15)
        output = result.stdout + result.stderr
        if result.returncode or "THURSDAY_ADAPTER_HISTORY_OK" not in output or any(error in output for error in ("FAIL!", "TypeError:", "ReferenceError:", "Failed to load configuration")):
            raise SystemExit(output)
        adapter = work / "shell/integrations/Thursday.qml"
        source = adapter.read_text().replace('    property string repoRoot:', '    property alias transportFixture: transport\n    property string repoRoot:')
        start = source.index('    Process {\n        id: transport')
        end = source.index('    Timer { id: startup;', start)
        adapter.write_text(source[:start] + '    QtObject { id: transport; property bool running: false; function write(data) {} }\n' + source[end:])
        (work / "shell/shell.qml").write_text('''import QtQuick
import Quickshell
import "integrations"
ShellRoot {
 Thursday { id: b; repoRoot: "" }
 FloatingWindow { visible: true; implicitWidth: 300; implicitHeight: 100 }
 Timer { interval: 100; running: true; onTriggered: {
  b.handle({type:"voice_state",data:{state:"submitted",session_id:"a",transcript:"hello"}});
  if (b.transcript !== "hello" || b.send({command:"message"}) || b.transcript !== "hello") { console.error("OFFLINE_FAIL"); Qt.exit(1); return; }
  b.transportFixture.running = true;
  if (!b.send({command:"message"}) || b.transcript !== "" || b.voiceSession !== "") { console.error("SEND_FAIL"); Qt.exit(1); return; }
  b.handle({type:"voice_state",data:{state:"submitted",session_id:"a",transcript:"late"}});
  if (b.transcript !== "") { console.error("LATE_FAIL"); Qt.exit(1); return; }
  console.info("TYPED_TEST_OK"); Qt.quit();
 } }
}''')
        result = subprocess.run(["qs", "-p", str(work / "shell")], env=env, capture_output=True, text=True, timeout=15)
        output = result.stdout + result.stderr
        if result.returncode or "TYPED_TEST_OK" not in output:
            raise SystemExit(output)
        print("PASS: full history, streaming, stale snapshot rejection, PCM ownership, microphone levels, options and acknowledgement")

if __name__ == "__main__":
    main()
