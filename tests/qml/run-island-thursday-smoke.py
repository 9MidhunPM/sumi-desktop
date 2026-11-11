#!/usr/bin/env python3
"""Verify the inline Thursday view against an inert backend; never record/send."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HARNESS = '''import QtQuick
import QtQuick.Controls
import QtTest
import Quickshell
import "components"
ShellRoot {
    property int fullRequests: 0
    property int dismissals: 0
    QtObject {
        id: backend
        property bool connected: false
        property bool ready: false
        property bool busy: false
        property bool taskActive: false
        property bool sendPending: false
        property bool recording: false
        property bool voiceActive: false
        property bool speaking: false
        property var playingAudio: null
        property bool resumable: false
        property var task: null
        property real visualizerLevel: 0
        property string activity: ""
        property var confirmations: []
        property string lastPrompt: ""
        property string submittedDraft: ""
        property string latestAnswer: ""
        property string transcript: ""
        property string errorText: ""
        property string voiceError: ""
        property string speechError: ""
        property string outputNotice: ""
        property string statusText: "Disconnected"
        property var prompts: []
        property var commands: []
        property var decisions: []
        property int microphones: 0
        property int stops: 0
        property int audioStops: 0
        function submit(text) { prompts = prompts.concat([text]); lastPrompt = text; submittedDraft = text; errorText = ""; sendPending = true; }
        function toggleMicrophone() { microphones++; recording = !recording; voiceActive = recording; }
        function decide(approved) { decisions = decisions.concat([{id:confirmations[0].id,approved:approved}]); }
        function stopTask() { stops++; }
        function stopAudio() { audioStops++; }
        function send(command) { commands = commands.concat([command]); }
    }
    FloatingWindow {
        id: window
        visible: true
        implicitWidth: 640
        implicitHeight: 440
        color: "#101014"
        IslandThursdayPage {
            id: page
            anchors.fill: parent
            anchors.margins: 12
            backend: null
            active: true
            onFullChatRequested: fullRequests++
            onDismissRequested: dismissals++
        }
        TestCase {
            name: "IslandThursday"
            when: true
            function check(value, message) { if (!value) { console.error("ISLAND_THURSDAY_FAILED", message); Qt.exit(1); throw new Error(message); } }
            function item(name) { const found = findChild(page,name); check(found !== null,"Missing "+name); return found; }
            function test_thursday() {
                wait(150);
                const composer = item("islandThursdayComposer");
                const send = item("islandThursdaySend");
                const mic = item("islandThursdayMicrophone");
                check(!send.enabled && !mic.enabled && item("islandThursdayStatus").text.indexOf("unavailable") >= 0,"Missing backend is truthful and inert");
                page.backend = backend;
                composer.text = "Keep my draft";
                page.focusDefault(); wait(40); keyClick(Qt.Key_Return);
                check(backend.prompts.length === 0 && composer.text === "Keep my draft", "Disconnected Enter preserves the draft");
                item("islandThursdayFullChat").clicked();
                check(fullRequests === 1, "Full conversation delegates through the parent signal");
                backend.connected = true;
                keyClick(Qt.Key_Return);
                check(backend.prompts.length === 0,"Starting backend cannot submit");
                backend.ready = true; backend.statusText = "Ready when you are";
                backend.activity = "Opening Downloads"; backend.taskActive = true;
                backend.task = {activities:[{id:"a1",tool:"hypruse__click_ui",label:"Opening Downloads",status:"running"}]};
                backend.visualizerLevel = 0.7; wait(30);
                check(item("islandThursdayStatus").text === "Opening Downloads", "Actual action replaces generic status");
                check(page.activities.length === 1 && item("islandThursdayActivityTimeline").visible, "Actual tool history is visible");
                check(item("islandThursdayOrb").level === 0.7, "Measured audio drives expanded orb");
                backend.taskActive = false; backend.statusText = "Speaking"; wait(10);
                check(item("islandThursdayStatus").text === "Speaking", "Completed action does not override live speech status");
                backend.statusText = "Ready when you are";
                backend.task = null; backend.activity = "";
                composer.text = "  Check my desktop  "; keyClick(Qt.Key_Return); wait(30);
                check(backend.prompts.join() === "Check my desktop" && composer.text === "  Check my desktop  ", "Enter submits one trimmed prompt while retaining the draft until acknowledgement");
                keyClick(Qt.Key_Return);
                check(backend.prompts.length === 1 && !send.enabled, "Send-pending blocks duplicate submissions");
                backend.sendPending = false;
                wait(30); check(composer.text.length > 0, "Ordered user_message alone cannot consume the draft before HTTP acknowledgement");
                backend.submittedDraft = ""; wait(30);
                check(composer.text === "", "Confirmed acceptance clears the matching submitted draft");
                composer.text = "First line"; composer.cursorPosition = composer.text.length;
                keyClick(Qt.Key_Return,Qt.ShiftModifier);
                check(composer.text.indexOf("\\n") >= 0 && backend.prompts.length === 1,"Shift Enter inserts a newline without sending");
                backend.busy = true; keyClick(Qt.Key_Return);
                check(backend.prompts.length === 1 && !send.enabled,"Working backend preserves the draft");
                backend.busy = false; backend.taskActive = true;
                check(!send.enabled,"Active task blocks competing prompt");
                item("islandThursdayStop").clicked(); check(backend.stops === 1,"Stop delegates to the existing task owner");
                backend.taskActive = false; composer.text = "";
                check(backend.microphones === 0,"Opening and typing never starts a microphone");
                mic.clicked();
                check(backend.microphones === 1 && page.recording && mic.selected,"Explicit microphone click starts the existing voice path");
                mic.clicked(); check(backend.microphones === 2 && !page.recording,"Finish uses the same voice path");
                backend.voiceActive = true; backend.transcript = "Actual words from the backend";
                composer.text = "Wait";
                check(!mic.enabled && !send.enabled && item("islandThursdayTranscript").text === backend.transcript,"Transcription blocks competing capture and shows actual text");
                backend.voiceActive = false;
                check(item("islandThursdayTranscript").parent.visible && item("islandThursdayTranscript").text === backend.transcript,"Actual latest voice transcript remains available after capture ends");
                const editTranscript = item("islandThursdayEditTranscript");
                const retryRecording = item("islandThursdayRetryRecording");
                const sentBeforeCorrection = backend.prompts.length;
                editTranscript.clicked(); wait(30);
                check(composer.text === backend.transcript && composer.activeFocus && backend.prompts.length === sentBeforeCorrection, "Edit transcript focuses a draft without submitting it");
                backend.busy = true;
                check(!editTranscript.enabled && !retryRecording.enabled, "Busy work disables transcript corrections");
                page.retryRecording(); check(backend.microphones === 2, "Guard prevents retries during work");
                backend.busy = false;
                retryRecording.clicked(); wait(30);
                check(backend.microphones === 3 && page.recording && backend.prompts.length === sentBeforeCorrection, "Retry explicitly starts a fresh recording without submitting preview text");
                page.retryRecording(); check(backend.microphones === 3, "Recording cannot start a competing retry");
                mic.clicked(); check(backend.microphones === 4 && !page.recording, "Retry finishes through the existing microphone control");
                composer.clear();
                backend.transcript = "";
                backend.speaking = true;
                item("islandThursdayStopAudio").clicked(); check(backend.audioStops === 1,"Speech stop delegates to the shared player");
                backend.speaking = false;
                backend.confirmations = [{id:"first",prompt:"Delete <b>this file</b>?"},{id:"second",prompt:"Run the next action?"}];
                check(item("islandThursdayApproval").text === backend.confirmations[0].prompt && item("islandThursdayApproval").textFormat === TextEdit.PlainText,"Approval shows the actual first prompt as plain text");
                item("islandThursdayApprove").clicked(); item("islandThursdayApprove").clicked();
                check(backend.decisions.length === 1 && backend.decisions[0].id === "first" && backend.decisions[0].approved && page.decisionPending,"Approval routes once to the current backend request");
                backend.confirmations = [backend.confirmations[1]];
                item("islandThursdayReject").clicked();
                check(backend.decisions.length === 2 && backend.decisions[1].id === "second" && !backend.decisions[1].approved,"Next request resets the guard and Reject routes correctly");
                backend.confirmations = [];
                backend.resumable = true; backend.task = {id:"fixture-task",status:"paused"};
                item("islandThursdayResume").clicked();
                check(backend.commands.length === 1 && backend.commands[0].command === "task_resume" && backend.commands[0].task_id === "fixture-task","Resume uses the native protocol and actual task ID");
                backend.task = {id:"invalid/task",status:"paused"}; page.resumeTask();
                check(backend.commands.length === 1 && !item("islandThursdayResume").enabled,"Invalid task references cannot be sent");
                backend.resumable = false; backend.task = null;
                backend.errorText = "Request failed"; backend.voiceError = "Microphone unavailable"; backend.speechError = "Request failed";
                check(item("islandThursdayError").text === "Request failed\\nMicrophone unavailable","Distinct real errors remain visible without duplicates");
                backend.latestAnswer = "A real streamed answer. ".repeat(120);
                backend.errorText = ""; backend.voiceError = ""; backend.speechError = "";
                for (const width of [640,320,280]) {
                    page.anchors.fill = null; page.width = width - 24; page.height = 416; wait(100);
                    check(item("islandThursdayAnswer").width <= page.width && composer.width <= page.width,"Answer and composer fit width "+width);
                    const location = send.mapToItem(page,0,0);
                    check(location.x + send.width <= page.width + 1 && location.y + send.height <= page.height + 1,"Send remains reachable at width "+width);
                }
                composer.text = "Please retry this"; page.submitPrompt();
                backend.errorText = "Request rejected"; backend.submittedDraft = ""; backend.sendPending = false;
                wait(30);
                check(composer.text === "Please retry this" && !page.awaitingSubmission,"Rejected submission preserves its draft for retry");
                backend.errorText = ""; page.submitPrompt();
                composer.text = "A newer unsent draft";
                backend.submittedDraft = ""; backend.sendPending = false; wait(30);
                check(composer.text === "A newer unsent draft","Acceptance never clears text edited after submission");
                composer.text = "Clear this after acceptance"; page.submitPrompt();
                backend.submittedDraft = ""; backend.sendPending = false; wait(30);
                check(composer.text === "", "Matching accepted prompt clears normally after a retry");
                const captureDir = Quickshell.env("SUMI_THURSDAY_CAPTURE_DIR");
                if (captureDir) {
                    page.width = 616;
                    backend.lastPrompt = "Help me organize my desktop.";
                    backend.latestAnswer = "I can help you arrange the workspace and review changes with you. What would you like to work on first?";
                    backend.confirmations = [{id:"visual-fixture",prompt:"Open the selected project folder in your file manager?"}];
                    backend.statusText = "Your approval is needed";
                    wait(100); grabImage(page).save(captureDir + "/island-thursday.png");
                    page.width = 296; wait(100);
                    grabImage(page).save(captureDir + "/island-thursday-narrow.png");
                    backend.confirmations = [];
                }
                page.focusDefault(); wait(40); keyClick(Qt.Key_Escape);
                check(dismissals === 1,"Escape delegates dismissal");
                backend.connected = false;
                check(item("islandThursdayConnection").text.indexOf("disconnected") >= 0 && !send.enabled && !mic.enabled,"Lost connection exposes truthful recovery and disables actions");
                check(backend.microphones === 4 && backend.prompts.length === 4,"Only explicit test actions used the fake backend");
                console.info("ISLAND_THURSDAY_OK"); Qt.quit();
            }
        }
    }
}
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sumi-thursday-') as temporary:
        work = Path(temporary)
        shell = work / 'shell'
        shutil.copytree(repo / 'shell', shell)
        (shell / 'shell.qml').write_text(HARNESS)
        runtime = work / 'runtime'
        runtime.mkdir(mode=0o700)
        env = dict(os.environ, SUMI_PREVIEW='1', QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(['qs', '-p', str(shell)], env=env, capture_output=True, text=True, timeout=15)
        output = result.stdout + result.stderr
        if result.returncode or 'ISLAND_THURSDAY_OK' not in output or any(error in output for error in ('TypeError:', 'ReferenceError:', 'Unable to assign [undefined]', 'Failed to load configuration', 'FAIL!', 'Binding loop')):
            raise SystemExit(output)
        print('PASS: null/disconnected truth; draft preservation; Enter/Shift Enter and send guards; explicit voice actions; approvals; task stop/resume protocol; plain-text response/errors; narrow layouts; full-chat/dismiss handoff')


if __name__ == '__main__':
    main()
