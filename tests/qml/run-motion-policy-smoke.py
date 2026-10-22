#!/usr/bin/env python3
"""Test the real motion policy/settings using private power and controller fixtures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


HARNESS = '''import QtQuick
import QtTest
import Quickshell
import Quickshell.Io
import "config"
import "fakepower" as Up
ShellRoot {
    id: root
    property var persisted: ({})
    FileView {
        id: saved
        path: Quickshell.env("SUMI_STATE_DIR") + "/settings.json"
        preload: true
        watchChanges: true
        printErrors: false
        onLoaded: root.persisted = JSON.parse(text())
        onFileChanged: reload()
    }
    Window {
        id: win
        width: 120; height: 80; visible: true
        TestCase {
            name: "SumiMotionPolicy"
            when: win.visible
            function check(value, message) {
                if (!value) { console.error("SUMI_MOTION_POLICY_FAILED", message); Qt.exit(1); throw new Error(message); }
            }
            function until(condition, message) {
                let elapsed = 0;
                while (!condition() && elapsed < 3000) { wait(20); elapsed += 20; }
                check(condition(), message);
            }
            function policy(mode, enter, exit, control) {
                check(Motion.mode === mode, "Expected mode " + mode + ", got " + Motion.mode);
                check(Motion.enter === enter && Motion.exit === exit && Motion.control === control,
                      "Durations for " + mode + ": " + [Motion.enter, Motion.exit, Motion.control]);
                check(Motion.reduced === (mode === "reduced"), "Reduced policy flag");
                check(Motion.expressive === (mode === "normal"), "Expressive policy flag");
                until(() => Motion.appliedMode === mode, "Private controller received " + mode);
                check(Motion.error === "", "Policy application stays healthy");
            }
            function persisted(full, reduced) {
                until(() => root.persisted.fullMotion === full && root.persisted.reducedMotion === reduced,
                      "Saved motion preference full=" + full + " reduced=" + reduced);
                check(Settings.fullMotion === full && Settings.reducedMotion === reduced, "File watcher preserves the selected mode");
                check(root.persisted.barHiddenMode && root.persisted.dnd, "Motion writes preserve unrelated settings");
                check(Settings.error === "", "Settings writes stay healthy");
            }
            function test_policy() {
                until(() => !Settings.loading, "Settings loaded");
                if (Quickshell.env("SUMI_MOTION_PHASE") === "reload") {
                    check(Settings.fullMotion && !Settings.reducedMotion, "Expressive override survived a fresh process");
                    Up.UPower.onBattery = true;
                    Up.PowerProfiles.profile = Up.PowerProfile.PowerSaver;
                    check(!Motion.battery, "Saved override still bypasses both battery signals");
                    policy("normal", 360, 200, 180);
                    persisted(true, false);
                    console.info("SUMI_MOTION_POLICY_RELOAD_OK");
                    Qt.quit();
                    return;
                }

                check(!Settings.fullMotion && !Settings.reducedMotion, "Legacy settings default to adaptive motion");
                check(Settings.barHiddenMode && Settings.dnd, "Legacy settings load normally");
                Up.UPower.onBattery = false;
                Up.PowerProfiles.profile = Up.PowerProfile.Balanced;
                check(!Motion.battery, "AC balanced is not battery motion");
                policy("normal", 360, 200, 180);
                Up.UPower.onBattery = true;
                check(Motion.battery, "Physical battery enables adaptive saving");
                policy("battery", 140, 110, 80);
                Up.UPower.onBattery = false;
                Up.PowerProfiles.profile = Up.PowerProfile.PowerSaver;
                check(Motion.battery, "Power saver enables adaptive saving even on AC");
                policy("battery", 140, 110, 80);
                Settings.fullMotion = true;
                check(!Motion.battery, "Explicit expressive overrides power saver");
                policy("normal", 360, 200, 180);
                Up.UPower.onBattery = true;
                check(!Motion.battery, "Explicit expressive overrides physical battery");
                policy("normal", 360, 200, 180);
                Settings.reducedMotion = true;
                policy("reduced", 0, 0, 0);
                Settings.fullMotion = false;
                policy("reduced", 0, 0, 0);
                Settings.reducedMotion = false;
                policy("battery", 140, 110, 80);

                Settings.cycleMotion();
                check(Settings.fullMotion && !Settings.reducedMotion, "Adaptive cycles to expressive");
                policy("normal", 360, 200, 180);
                persisted(true, false);
                Settings.cycleMotion();
                check(!Settings.fullMotion && Settings.reducedMotion, "Expressive cycles to reduced");
                policy("reduced", 0, 0, 0);
                persisted(false, true);
                Settings.cycleMotion();
                check(!Settings.fullMotion && !Settings.reducedMotion, "Reduced cycles to adaptive");
                policy("battery", 140, 110, 80);
                persisted(false, false);
                Settings.setValue("fullMotion", true);
                policy("normal", 360, 200, 180);
                persisted(true, false);
                console.info("SUMI_MOTION_POLICY_MATRIX_OK");
                Qt.quit();
            }
        }
    }
}
'''


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sumi-motion-policy-') as temporary:
        work = Path(temporary)
        shell = work / 'shell'
        config = shell / 'config'
        power = shell / 'fakepower'
        state = work / 'state'
        runtime = work / 'runtime'
        for directory in (config, power, state, runtime):
            directory.mkdir(parents=True, mode=0o700)
        shutil.copy2(repo / 'shell/config/Settings.qml', config / 'Settings.qml')
        motion = (repo / 'shell/config/Motion.qml').read_text()
        original_import = 'import Quickshell.Services.UPower as Up'
        if motion.count(original_import) != 1:
            raise SystemExit('Motion physical-power fixture import needs updating')
        (config / 'Motion.qml').write_text(motion.replace(original_import, 'import "../fakepower" as Up', 1))
        (config / 'qmldir').write_text('singleton Settings Settings.qml\nsingleton Motion Motion.qml\n')
        (power / 'qmldir').write_text('singleton UPower UPower.qml\nsingleton PowerProfiles PowerProfiles.qml\nPowerProfile PowerProfile.qml\n')
        (power / 'UPower.qml').write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool onBattery: false }\n')
        (power / 'PowerProfiles.qml').write_text('pragma Singleton\nimport QtQuick\nQtObject { property int profile: PowerProfile.Balanced }\n')
        (power / 'PowerProfile.qml').write_text('import QtQuick\nQtObject { enum Profile { Balanced, PowerSaver } }\n')
        (shell / 'shell.qml').write_text(HARNESS)
        settings = state / 'settings.json'
        settings.write_text(json.dumps({'version': 1, 'barHiddenMode': True, 'reducedMotion': False, 'dnd': True}))
        settings.chmod(0o600)
        controller = work / 'desktopctl-fixture'
        controller.write_text(f'#!{sys.executable}\n' + '''import json, os, sys
from pathlib import Path
arguments = sys.argv[1:]
if arguments[:2] != ['motion', 'apply'] or arguments[2] not in ('normal', 'battery', 'reduced') or arguments[3:] != ['--json']:
    raise SystemExit('Unexpected fixture command')
with (Path(os.environ['SUMI_STATE_DIR']) / 'applied.jsonl').open('a') as output:
    output.write(json.dumps(arguments) + '\\n')
print('{}')
''')
        controller.chmod(0o700)
        environment = dict(os.environ, HOME=str(work), XDG_CONFIG_HOME=str(work / 'config'),
                           SUMI_PREVIEW='0', SUMI_STATE_DIR=str(state), SUMI_DESKTOPCTL=str(controller),
                           QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                           QT_LOGGING_TO_CONSOLE='1', QT_FORCE_STDERR_LOGGING='1', XDG_RUNTIME_DIR=str(runtime),
                           DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(work / 'absent-bus'))
        for phase in ('matrix', 'reload'):
            environment['SUMI_MOTION_PHASE'] = phase
            result = subprocess.run(['qs', '-p', str(shell), '-n'], env=environment, capture_output=True, text=True, timeout=15)
            output = result.stdout + result.stderr
            marker = 'SUMI_MOTION_POLICY_' + phase.upper() + '_OK'
            if result.returncode or marker not in output or any(value in output for value in ('FAIL!', 'TypeError:', 'ReferenceError:', 'Failed to load configuration', 'Unable to assign [undefined]', 'Binding loop')):
                raise SystemExit(f'Motion policy {phase} failed, exit {result.returncode}:\n{output}')
        persisted = json.loads(settings.read_text())
        assert persisted['fullMotion'] is True and persisted['reducedMotion'] is False, persisted
        applied = [json.loads(line)[2] for line in (state / 'applied.jsonl').read_text().splitlines()]
        assert set(applied) == {'normal', 'battery', 'reduced'} and applied[-1] == 'normal', applied
        print('PASS motion policy: AC/battery/power saver; expressive override; reduced priority; durations; full cycle; real settings persistence and fresh-process reload')


if __name__ == '__main__':
    main()
