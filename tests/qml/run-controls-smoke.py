#!/usr/bin/env python3
"""Exercise shared controls with an inert controller and synthetic observations."""
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import threading

HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "services" as S
ShellRoot {
    property int changes: 0
    property var recordingCompletions: []
    Connections { target: S.Recording; function onCompleted(operation, result) { recordingCompletions = recordingCompletions.concat([operation]); } }
    Connections { target: S.Brightness; function onChanged(value) { changes++; } }
    Window {
        id: win
        visible: true; width: 240; height: 100
        TestCase {
            name: "SharedControls"
            when: win.visible
            function check(value, message) { if (!value) { console.error("SUMI_CONTROLS_FAILED", message); Qt.exit(1); throw new Error(message); } }
            function count(name) { return S.Desktop.requests.filter(item => item.name === name).length; }
            function test_controls() {
                check(S.Desktop.requests.length === 0, "Preview environment starts no observers or recovery commands");
                S.Brightness.refresh();
                S.Desktop.respond("brightness-get", true, {percent:40});
                check(changes === 0, "Initial command read is silent");
                S.Brightness.observedLine('{"available":true,"percent":40}');
                check(S.Brightness.ready && S.Brightness.percent === 40 && changes === 0, "Observer baseline is useful and silent");
                S.Brightness.observedLine('{"available":true,"percent":40}');
                S.Brightness.observedLine('{"available":true,"percent":55}');
                check(changes === 1 && S.Brightness.percent === 55, "Hardware observations deduplicate and publish real changes");
                S.Brightness.refresh();
                S.Brightness.observedLine('{"available":true,"percent":60}');
                S.Desktop.respond("brightness-get", true, {percent:55});
                check(S.Brightness.percent === 60, "Old command reads cannot overwrite a newer hardware observation");
                S.Brightness.refresh(); S.Brightness.refresh();
                check(count("brightness-get") === 1, "Controls share a single read");
                S.Brightness.setPercent(65);
                S.Desktop.respond("brightness-get", true, {percent:55});
                check(S.Brightness.percent === 65, "Stale read cannot undo an adjustment");
                wait(90);
                S.Brightness.setPercent(70); S.Brightness.setPercent(80); wait(90);
                check(count("brightness") === 1, "Writes serialize across controls");
                S.Desktop.respond("brightness", true, {});
                check(S.Desktop.requests.find(item => item.name === "brightness").args[0] === 80, "Latest pending target wins");
                S.Desktop.respond("brightness", true, {});
                S.Desktop.respond("brightness-get", true, {percent:80});
                check(S.Brightness.percent === 80 && !S.Brightness.busy, "State converges after writes");
                const beforeObservedSuccess = changes;
                S.Brightness.observedLine('{"available":true,"percent":80}');
                check(changes === beforeObservedSuccess + 1, "Command read cannot consume an actual watcher success event");
                const beforeFailedWrite = changes;
                S.Brightness.setPercent(90); wait(90);
                check(changes === beforeFailedWrite, "Optimistic slider changes publish no success");
                S.Desktop.respond("brightness", false, {}, "Permission denied");
                S.Desktop.respond("brightness-get", true, {percent:80});
                S.Brightness.observedLine('{"available":true,"percent":80}');
                check(changes === beforeFailedWrite && S.Brightness.percent === 80, "Failed write restores observed state without success feedback");
                S.Brightness.observedLine('{"available":false,"error":"Backlight disconnected"}');
                check(!S.Brightness.available && S.Brightness.error.length > 0, "Removed hardware disables all controls");
                S.NightLight.refresh();
                S.Desktop.respond("night-light-get", true, {available:true, active:false});
                S.NightLight.toggle(); S.NightLight.toggle();
                check(count("night-light") === 1 && !S.NightLight.active, "Toggle is guarded and waits for confirmation");
                S.Desktop.respond("night-light", false, {}, "Rejected");
                S.Desktop.respond("night-light-get", true, {available:true, active:false});
                check(S.NightLight.error === "Rejected" && !S.NightLight.active, "Failed toggle reconciles without hiding its error");
                S.Recording.refresh();
                S.Desktop.respond("record", true, {recording:false});
                let released = false;
                S.Recording.start(function(ok, result, error) { released = true; check(ok && result.cancelled === true, "Cancellation callback carries the result"); });
                check(!released && S.Recording.busy, "Selector handoff remains held until completion");
                S.Desktop.respond("record", true, {recording:false,cancelled:true});
                check(released && !S.Recording.recording && !S.Recording.busy, "Cancelled selector releases shared state");
                check(recordingCompletions.length === 0, "Cancelled start creates no completion message");
                S.Recording.start();
                S.Desktop.respond("record", true, {recording:true,file:"/tmp/fixture.mp4"});
                check(recordingCompletions.join() === "start", "Confirmed start creates one completion");
                check(S.Recording.recording && S.Recording.file === "/tmp/fixture.mp4", "Successful start publishes an owned recording");
                for (let attempt = 0; attempt < 65 && count("record") === 0; attempt++) wait(100);
                check(count("record") === 1, "Only active recording checks status at five seconds (pending=" + count("record") + ")");
                S.Desktop.respond("record", true, {recording:false});
                wait(5600);
                check(count("record") === 0 && !S.Recording.recording, "Recorder exit is discovered and idle polling stops");
                check(recordingCompletions.join() === "start", "Status recovery after recorder exit never claims a saved file");
                S.Recording.start();
                S.Desktop.respond("record", true, {recording:true,file:"/tmp/fixture.mp4"});
                S.Recording.stop();
                S.Desktop.respond("record", true, {recording:false,file:"/tmp/fixture.mp4",stopped:false});
                check(recordingCompletions.join() === "start,start", "Stopping a stale receipt never claims successful save");
                S.Recording.refresh();
                S.Desktop.respond("record", true, {recording:true,file:"/tmp/fixture.mp4"});
                S.Recording.stop();
                S.Desktop.respond("record", true, {recording:false,file:"/tmp/fixture.mp4",stopped:true});
                S.Recording.stop();
                check(recordingCompletions.join() === "start,start,stop" && count("record") === 0, "Confirmed stop emits once and repeated Stop is inert");
                S.Desktop.preview = true;
                S.Brightness.setPercent(90); S.Brightness.refresh();
                S.NightLight.toggle(); S.NightLight.refresh();
                released = false;
                S.Recording.start(function(ok) { released = true; check(!ok, "Preview rejects recording"); });
                S.Recording.stop(); S.Recording.refresh();
                check(released && S.Desktop.requests.length === 0, "Preview performs no hardware writes or reads");
                console.info("SUMI_SHARED_CONTROLS_OK"); Qt.quit();
            }
        }
    }
}
'''


RECEIPT_HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "services" as S
ShellRoot {
    Window {
        id: win
        visible: true; width: 100; height: 100
        TestCase {
            name: "RecordingReceipt"
            when: win.visible
            function test_receipt() {
                verify(S.Recording.busy);
                S.Desktop.respond("record", true, {recording:false});
                wait(1700);
                compare(S.Desktop.requests.filter(item => item.name === "record").length, 1);
                S.Desktop.respond("record", true, {recording:true,file:"/tmp/fixture"});
                verify(S.Recording.recording);
                wait(1400);
                compare(S.Desktop.requests.filter(item => item.name === "record").length, 1);
                S.Desktop.respond("record", true, {recording:false});
                verify(!S.Recording.recording);
                console.info("SUMI_RECEIPT_WATCH_OK"); Qt.quit();
            }
        }
    }
}
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    fake_desktop = runpy.run_path(str(repo / 'tests/qml/run-quick-settings-smoke.py'))['DESKTOP']
    with tempfile.TemporaryDirectory(prefix='sumi-controls-') as temporary:
        work = Path(temporary)
        config = work / 'shell'
        shutil.copytree(repo / 'shell', config)
        (config / 'services/Desktop.qml').write_text(fake_desktop)
        (config / 'shell.qml').write_text(HARNESS)
        runtime = work / 'runtime'
        runtime.mkdir(mode=0o700)
        env = dict(os.environ, SUMI_PREVIEW='1', QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(['qs', '-p', str(config)], env=env, capture_output=True, text=True, timeout=20)
        output = result.stdout + result.stderr
        if result.returncode or 'SUMI_SHARED_CONTROLS_OK' not in output or any(error in output for error in ('TypeError:', 'ReferenceError:', 'FAIL!', 'Failed to load configuration', 'Unable to assign [undefined]', 'Binding loop')):
            raise SystemExit(output)
        # Exercise actual file watching in a temporary runtime directory. Only
        # the receipt observer is enabled; the Desktop controller remains inert.
        recording = config / 'services/Recording.qml'
        recording.write_text(recording.read_text().replace('!Desktop.preview && Quickshell.env("SUMI_PREVIEW") !== "1" && runtimeDir.length > 0', 'true'))
        (config / 'shell.qml').write_text(RECEIPT_HARNESS)
        (runtime / 'sumi').mkdir()
        receipt = runtime / 'sumi/recorder.json'
        create = threading.Timer(1, lambda: receipt.write_text('{"pid":123,"file":"/tmp/fixture"}'))
        remove = threading.Timer(2.3, lambda: receipt.unlink())
        create.start(); remove.start()
        try:
            result = subprocess.run(['qs', '-p', str(config)], env=env, capture_output=True, text=True, timeout=10)
        finally:
            create.join(); remove.join()
        output = result.stdout + result.stderr
        if result.returncode or 'SUMI_RECEIPT_WATCH_OK' not in output or any(error in output for error in ('TypeError:', 'ReferenceError:', 'FAIL!', 'Failed to load configuration', 'Unable to assign [undefined]', 'Binding loop')):
            raise SystemExit(output)
        print('PASS: receipt creation/deletion discovers external recorder starts/exits without idle polling')
        print('PASS: silent/deduplicated backlight observations; shared serialized writes; hardware removal; confirmed night light; recording selector callback/cancel; active-only recovery checks; preview isolation')


if __name__ == '__main__':
    main()
