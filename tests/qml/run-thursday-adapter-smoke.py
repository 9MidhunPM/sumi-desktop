#!/usr/bin/env python3
"""Validate the portable companion against an isolated JSON-lines fixture."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HARNESS = r'''import QtQuick
import QtTest
import Quickshell
import "integrations" as I
import "integrations/SpeechLevels.js" as Speech
ShellRoot {
    I.Thursday { id: backend }
    TestCase {
        when: true
        function check(value, label) { if (!value) { console.error("THURSDAY_ADAPTER_FAILED", label); Qt.exit(1); throw new Error(label); } }
        function test_portable() {
            if (Quickshell.env("ADAPTER_UNCONFIGURED") === "1") {
                wait(100);
                check(!backend.configured && !backend.requested && !backend.connected, "Unconfigured startup creates no companion");
                backend.connectHelper();
                check(!backend.requested && backend.errorText.indexOf("SUMI_THURSDAY_ROOT") >= 0, "Optional setup has an honest unavailable state");
                console.info("THURSDAY_ADAPTER_OK"); Qt.quit(); return;
            }
            for (let elapsed = 0; !backend.connected && elapsed < 2500; elapsed += 20) wait(20);
            check(backend.connected && backend.ready && backend.requested, "Configured integration connects without a hardcoded path");
            check(backend.latestAnswer === "", "Archived history never replays as a fresh answer");
            backend.submit("A portable request");
            for (let elapsed = 0; !backend.latestAnswer || backend.submittedDraft; elapsed += 20) { wait(20); if (elapsed > 2500) break; }
            check(backend.latestAnswer === "A portable response" && backend.lastPrompt === "A portable request" && !backend.sendPending && !backend.submittedDraft, "Streaming answer and draft acknowledgement follow helper protocol");
            backend.handle({type:"confirm_required",data:{id:"first",prompt:"Review first"}});
            backend.handle({type:"confirm_required",data:{id:"second",prompt:"Review second"}});
            backend.decide(false); wait(50);
            check(backend.confirmations.length === 1 && backend.confirmations[0].id === "second", "Only the first explicit approval is decided");
            backend.handle({type:"voice_state",data:{state:"listening",session_id:"voice",transcript:""}});
            check(backend.voiceActive && backend.recording, "Voice state drives the island");
            backend.handle({type:"voice_state",data:{state:"idle",session_id:"voice",transcript:"Measured words"}});
            check(!backend.voiceActive && backend.transcript === "Measured words", "Voice transcript remains separate from the answer");
            const envelope = {interval_ms:20,levels:[0,.2,.4,0,.8]};
            const measured = Speech.reading(envelope,40,true,4);
            check(measured.available && measured.level === .4 && measured.bars.join() === "0,0,0.2,0.4", "Speech reads measured milliseconds without future samples");
            check(Speech.reading(envelope,60,true,4).bars.every(value => value === 0), "Current silence flattens all bars");
            check(!Speech.reading(envelope,400,true,4).available && !Speech.reading(envelope,40,false,4).available, "Stopped or exhausted speech invents no levels");
            backend.handle({type:"tts_audio",data:{client_id:"native",local_url:"https://invalid.example/audio",generation_id:"unsafe"}});
            check(!backend.playingAudio && backend.audioQueue.length === 0 && !backend.speaking, "Only helper-local audio can play");
            // A fixture voice engine makes real helper feedback observable
            // without creating an audio device or reading any audio file.
            backend.handle({type:"native_output",data:{known:true,audible:false}});
            backend.handle({type:"tts_audio",data:{client_id:"native",local_url:"file:///fixture/first.mp3",audio_id:"first",generation_id:"queued-voice"}});
            backend.handle({type:"tts_audio",data:{client_id:"native",local_url:"file:///fixture/second.mp3",audio_id:"second",generation_id:"queued-voice"}});
            wait(40);
            check(backend.playbackRunning && !backend.speaking, "Playback without an observed audible route never claims speaking");
            backend.send({command:"health",marker:"before-audible"});
            backend.handle({type:"native_output",data:{known:true,audible:true}});
            check(backend.speaking, "Observed audibility enables speaking feedback");
            wait(320);
            check(!backend.playingAudio && backend.audioQueue.length === 0 && !backend.speaking, "Two queued chunks drain completely");
            backend.send({command:"health",marker:"after-drain"});
            backend.openChat(); wait(50);
            check(backend.opened, "Full conversation requests the island surface");
            backend.disconnect(); wait(50);
            check(!backend.connected && !backend.ready && !backend.requested && !backend.speaking, "Explicit disconnect releases the helper and speaking state");
            console.info("THURSDAY_ADAPTER_OK"); Qt.quit();
        }
    }
}
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-thursday-adapter-") as temporary:
        work = Path(temporary)
        shutil.copytree(repo / "shell/integrations", work / "integrations")
        # A missing audio component must not break optional or text-only use.
        (work / "integrations/ThursdayAudio.qml").unlink()
        (work / "shell.qml").write_text(HARNESS)
        companion = work / "companion"
        companion.mkdir()
        commands = work / "commands.jsonl"
        helper = work / "fixture-python"
        helper.write_text(f'''#!{sys.executable}
import json, sys
from pathlib import Path
commands = Path({str(commands)!r})
def emit(kind, data): print(json.dumps({{"type":kind,"data":data}}),flush=True)
emit("native_connection",{{"connected":True}})
emit("init",{{"model_ready":True,"conversation_id":7,"history":[{{"role":"assistant","content":"Archived"}}]}})
for line in sys.stdin:
    value=json.loads(line)
    with commands.open("a") as output: output.write(json.dumps(value)+"\\n")
    kind=value.get("command")
    if kind=="message":
        emit("user_message",{{"content":value["prompt"],"conversation_id":7}})
        emit("token",{{"chunk":"A portable "}})
        emit("final_response",{{"content":"A portable response"}})
        emit("native_command_result",{{"command":"message"}})
    elif kind=="confirm": emit("confirm_resolved",{{"id":value["id"]}})
''')
        helper.chmod(0o700)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        base = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime), SUMI_PREVIEW="0")
        environments = [dict(base, SUMI_THURSDAY_ROOT="", SUMI_THURSDAY_PYTHON="", ADAPTER_UNCONFIGURED="1"),
                        dict(base, SUMI_THURSDAY_ROOT=str(companion), SUMI_THURSDAY_PYTHON=str(helper), ADAPTER_UNCONFIGURED="0")]
        for env in environments:
            if env["ADAPTER_UNCONFIGURED"] == "0":
                (work / "integrations/ThursdayAudio.qml").write_text('''import QtQuick
import Quickshell
Scope {
    id: engine
    property url source: ""
    property bool muted: false
    property int position: 0
    readonly property bool playing: source.toString().length > 0 && !muted
    signal finished(bool failed)
    onSourceChanged: { completion.stop(); if (source.toString()) completion.start(); }
    Timer { id: completion; interval: 120; onTriggered: engine.finished(false) }
}
''')
            try:
                result = subprocess.run(["qs", "-p", str(work)], env=env, text=True, capture_output=True, timeout=12)
            except subprocess.TimeoutExpired as error:
                raise SystemExit((error.stdout or b"").decode() + (error.stderr or b"").decode())
            output = result.stdout + result.stderr
            if result.returncode or "THURSDAY_ADAPTER_OK" not in output or any(error in output for error in ("TypeError:","ReferenceError:","Binding loop","Unable to assign [undefined]","Failed to load configuration","FAIL!")):
                raise SystemExit(output)
        recorded = [json.loads(line) for line in commands.read_text().splitlines()]
        confirmations = [item for item in recorded if item["command"] == "confirm"]
        if confirmations != [{"command":"confirm","id":"first","approved":False}] or any(item["command"] == "open_web" for item in recorded):
            raise SystemExit(f"Unexpected explicit command routing: {recorded}")
        voice = [item for item in recorded if item.get("generation_id") == "queued-voice"]
        states = [item["state"] for item in voice if item["command"] == "playback"]
        before_audible = next(index for index, item in enumerate(recorded) if item.get("marker") == "before-audible")
        if any(item.get("state") == "playing" and item.get("generation_id") == "queued-voice" for item in recorded[:before_audible]):
            raise SystemExit("Silent route incorrectly reported playing")
        release_order = [item["audio_id"] for item in recorded if item["command"] == "audio_release" and item.get("audio_id") in {"first", "second"}]
        idle_positions = [index for index, item in enumerate(recorded) if item.get("generation_id") == "queued-voice" and item.get("state") == "idle"]
        second_release = next(index for index, item in enumerate(recorded) if item.get("audio_id") == "second")
        if "playing" not in states or not idle_positions or idle_positions[0] < second_release or release_order != ["first", "second"]:
            raise SystemExit(f"Queued speech feedback lifecycle is incorrect: {recorded}")
        print("PASS: queued speech retains active playback until final drain; playing requires observed audibility")
        print("PASS: no-config isolation; configured helper stream; draft acknowledgement; first explicit approval; voice state; measured silent-safe speech; local audio boundary; inline full-chat request and disconnect")


if __name__ == "__main__":
    main()
