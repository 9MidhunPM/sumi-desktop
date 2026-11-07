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
        TestCase {
            name: "IslandAssistantOutput"
            when: true
            function check(value, message) { if (!value) { console.error("ISLAND_ASSISTANT_OUTPUT_FAILED", message); Qt.exit(1); throw new Error(message); } }
            function test_output() {
                try {
                Settings.reducedMotion = true;
                wait(100);
                const response = findChild(output,"islandAssistantOutputText");
                const scroll = findChild(output,"islandAssistantOutputScroll");
                check(response.readOnly && response.selectByMouse && response.textFormat === TextEdit.PlainText,"Response is selectable read-only plain text");
                check(response.text === output.text && !response.activeFocusOnTab,"Output contains actual response and never requests keyboard focus");
                response.select(0,4); check(response.selectedText === "This","Actual response text can be selected");
                check(findChild(output,"islandThursdayComposer") === null && findChild(output,"islandThursdaySend") === null,"No composer or full-chat actions are included");
                const shortHeight = output.preferredHeight;
                output.text = "Literal <b>plain text</b> and a long response that wraps to the supplied width. ".repeat(80);
                wait(100);
                check(response.text.indexOf("<b>plain text</b>") >= 0 && response.contentHeight > scroll.height,"Long actual output wraps and scrolls without markup rendering");
                check(output.preferredHeight === 260 && shortHeight < output.preferredHeight,"Output height grows to a bounded cap");
                output.height = 160; wait(30);
                check(output.preferredHeight === 260,"Preferred height is independent of allocated height");
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
                check(!output.visible,"Inactive output is unmapped");
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
