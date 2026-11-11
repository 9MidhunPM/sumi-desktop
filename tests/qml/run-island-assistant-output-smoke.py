#!/usr/bin/env python3
"""Verify response-only island output using real Qt text and measured fixtures."""
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
import "config"
ShellRoot {
    FloatingWindow {
        id: window
        visible: true
        implicitWidth: 560
        implicitHeight: 320
        color: "#080809"
        IslandAssistantOutput {
            id: output
            x: 20; y: 20
            width: 520
            height: implicitHeight
            active: true
            text: "This is the actual Thursday response."
        }
        IslandVoicePreview {
            id: voice
            x: 20; y: 20; width: 400; height: 122
            active: true; phase: "listening"; partialTranscript: "Partial words"; level: 0.6
        }
        TestCase {
            name: "IslandAssistantOutput"
            when: true
            function check(value, message) { if (!value) { console.error("ISLAND_ASSISTANT_OUTPUT_FAILED", message); Qt.exit(1); throw new Error(message); } }
            function test_output() {
                try {
                Settings.reducedMotion = true;
                wait(100);
                const heard = findChild(voice, "islandVoiceHeard");
                const answer = findChild(voice, "islandVoiceAnswer");
                const footer = findChild(voice, "islandVoiceFooter");
                const button = findChild(voice, "islandVoiceOpen");
                const voiceOrb = findChild(voice, "islandVoiceOrb");
                function clearOfFooter(item) {
                    const textY = item.mapToItem(voice, 0, 0).y;
                    const footerY = footer.mapToItem(voice, 0, 0).y;
                    return textY + item.height <= footerY && footerY + footer.height <= voice.height;
                }
                check(clearOfFooter(heard), "Listening text remains above footer at 170px host height");
                check(footer.mapToItem(voice,0,0).x + footer.width <= button.mapToItem(voice,0,0).x, "Footer text does not overlap action");
                check(heard.text === "Partial words", "Listening shows the actual provisional words");
                check(voiceOrb.visible && voiceOrb.active && voiceOrb.level === 0.6 && heard.x + heard.width <= voiceOrb.x, "Measured listening orb sits right of the transcript");
                voice.finalTranscript = "Final corrected words"; voice.phase = "thinking"; wait(20);
                check(heard.text === "Final corrected words", "Thinking keeps final recognition");
                check(voiceOrb.processing && !voiceOrb.active, "Thinking indicates processing without inventing audio");
                voice.height = 156; voice.answer = "Actual response"; voice.phase = "speaking"; wait(20);
                check(heard.text === "Heard: Final corrected words" && answer.visible && answer.text === voice.answer, "Speech retains final heard text alongside reply");
                check(voiceOrb.active && voiceOrb.width === 120 && answer.x + answer.width <= voiceOrb.x && button.x + button.width <= voiceOrb.x && Math.abs(voiceOrb.y + voiceOrb.height / 2 - voice.height / 2) < .1, "Larger speaking orb is centered and stays clear of text and footer");
                voice.orbCenterY = 56; wait(20);
                check(Math.abs(voiceOrb.y + voiceOrb.height / 2 - 56) < .1, "Host can center the orb in the whole island");
                check(clearOfFooter(answer), "Reply stays above footer at 204px host height");
                check(heard.y + heard.height <= answer.y, "Heard and response text do not overlap");
                voice.width = 240; wait(20);
                check(heard.width <= voice.width && answer.width <= voice.width && clearOfFooter(answer) && footer.mapToItem(voice,0,0).x + footer.width <= button.mapToItem(voice,0,0).x, "Voice text and action stay bounded without collision at narrow widths");
                check(answer.x + answer.width <= voiceOrb.x && voiceOrb.reducedMotion, "Narrow orb remains separate and respects reduced motion");
                voice.phase = "error"; wait(20);
                check(!voiceOrb.active && !voiceOrb.processing, "Error does not imply recording or processing");
                voice.active = false; check(!voice.visible, "Inactive voice preview is hidden");
                const response = findChild(output,"islandAssistantOutputText");
                const scroll = findChild(output,"islandAssistantOutputScroll");
                check(response.readOnly && response.selectByMouse && response.textFormat === TextEdit.PlainText,"Response is selectable read-only plain text");
                check(response.text === output.text && !response.activeFocusOnTab,"Output contains actual response and never requests keyboard focus");
                response.select(0,4); check(response.selectedText === "This","Actual response text can be selected");
                check(findChild(output,"islandThursdayComposer") === null && findChild(output,"islandThursdaySend") === null,"No composer or full-chat actions are included");
                const orb = findChild(output,"islandAssistantOutputOrb");
                check(orb !== null && orb.width === 160, "Expanded response has the shared 160px orb");
                output.level = 0.6; wait(30);
                check(orb.level === 0.6, "Orb is driven by measured audio");
                const shortHeight = output.preferredHeight;
                output.text = "Literal <b>plain text</b> and a long response that wraps to the supplied width. ".repeat(80);
                wait(100);
                check(response.text.indexOf("<b>plain text</b>") >= 0 && response.contentHeight > scroll.height,"Long actual output wraps and scrolls without markup rendering");
                check(output.preferredHeight === 440 && shortHeight < output.preferredHeight,"Output height grows to a bounded cap");
                output.height = 160; wait(30);
                check(output.preferredHeight === 440,"Preferred height is independent of allocated height");
                output.width = 280; wait(30);
                check(response.width <= output.width && scroll.width <= output.width,"Narrow response stays within its viewport");
                const narrowContentHeight = response.contentHeight;
                output.width = 520; wait(30);
                check(response.contentHeight < narrowContentHeight,"Wrapping follows the supplied width");
                output.text = "An actual response, without controls or a conversation window.";
                output.height = Qt.binding(() => output.implicitHeight);
                const sender = findChild(output,"islandAssistantOutputSender");
                check(sender.visible && sender.text === "Thursday:", "Sender identifies the actual Thursday response");
                check(scroll.y >= sender.y + sender.height && scroll.height > 0, "Response viewport follows sender without a footer");
                output.speaking = true; output.samples = Array(20).fill(100); wait(30);
                check(findChild(output,"islandAssistantOutputWave") === null && findChild(output,"islandAssistantOutputBar0") === null, "No duplicate speech visualization is created");
                const captureDir = Quickshell.env("SUMI_ASSISTANT_OUTPUT_CAPTURE_DIR");
                if(captureDir) grabImage(output).save(captureDir+"/island-assistant-output.png");
                output.active = false; wait(20);
                check(!output.visible && !orb.active,"Inactive output and animation are unmapped");
                output.active = true; output.speaking = false; wait(20);
                check(response.text === output.text && sender.text === "Thursday:", "Actual response remains readable independently of playback");
                console.info("ISLAND_ASSISTANT_OUTPUT_OK"); Qt.quit();
                } catch(error) { console.error("OUTPUT_EXCEPTION",String(error),error.stack); Qt.exit(1); throw error; }
            }
        }
    }
}
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sumi-assistant-output-') as temporary:
        work = Path(temporary)
        shell = work / 'shell'
        shutil.copytree(repo / 'shell', shell)
        (shell / 'shell.qml').write_text(HARNESS)
        runtime = work / 'runtime'
        runtime.mkdir(mode=0o700)
        env = dict(os.environ, SUMI_PREVIEW='1', QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(['qs','-p',str(shell)],env=env,capture_output=True,text=True,timeout=12)
        text = result.stdout + result.stderr
        if result.returncode or 'ISLAND_ASSISTANT_OUTPUT_OK' not in text or any(error in text for error in ('TypeError:','ReferenceError:','Unable to assign [undefined]','Failed to load configuration','FAIL!','Binding loop')):
            raise SystemExit(text)
        print('PASS: actual selectable plain-text response only; long/narrow wrapping and bounded height; Thursday sender; no duplicate footer visualization; playback-independent response; inactive visibility')


if __name__ == '__main__':
    main()
