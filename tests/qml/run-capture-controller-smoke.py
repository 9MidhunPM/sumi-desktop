#!/usr/bin/env python3
"""Exercise real capture controller callbacks with inert selector/recorder tools."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import sys

RECORDER = r'''#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static volatile sig_atomic_t finished = 0;
static void stop(int signum) { finished = 1; }
int main(int argc, char **argv) {
    if (strcmp(getenv("SUMI_CAPTURE_TEST_MODE"), "failure") == 0) {
        fprintf(stderr, "Synthetic recorder startup failure\n");
        return 2;
    }
    const char *filename = NULL;
    for (int i = 1; i + 1 < argc; i++) if (!strcmp(argv[i], "-f")) filename = argv[i + 1];
    if (!filename) return 3;
    FILE *file = fopen(filename, "w");
    if (!file) return 4;
    fputs("INERT TEST FIXTURE; NO SCREEN CAPTURE", file);
    fclose(file);
    file = fopen(getenv("SUMI_CAPTURE_TEST_PID"), "w");
    if (file) { fprintf(file, "%d", getpid()); fclose(file); }
    signal(SIGINT, stop);
    while (!finished) pause();
    return 0;
}
'''

SELECTOR = '''#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import time
Path(os.environ["SUMI_CAPTURE_TEST_SELECTOR_PID"]).write_text(str(os.getpid()))
mode = os.environ['SUMI_CAPTURE_TEST_MODE']
if mode == 'timeout':
    time.sleep(30)
if mode == 'escape':
    raise SystemExit(1)
if mode != 'empty':
    print('0,0 100x100')
'''

HARNESS = '''import QtQuick
import Quickshell
import "services" as S
ShellRoot {
    id: root
    property bool nativeDialogOpen: false
    property bool started: false
    property bool returned: false
    property bool stopRequested: false
    readonly property string mode: Quickshell.env("SUMI_CAPTURE_TEST_MODE")
    property int ticks: 0
    function check(value, message) { if (!value) { console.error("CAPTURE_CONTROLLER_FAILED", mode, message); Qt.exit(1); } }
    Timer {
        interval: 40; repeat: true; running: true
        onTriggered: {
            if (++root.ticks > 150) { root.check(false,"Controller did not return promptly"); return; }
            if (!root.started && S.Recording.ready && !S.Recording.busy) {
                root.started = true; root.nativeDialogOpen = true;
                S.Recording.start(function(ok, result, error) {
                    root.returned = true;
                    root.nativeDialogOpen = false;
                    if (root.mode === "success") {
                        root.check(ok && result.recording && S.Recording.recording,"Real controller returns while detached fixture recorder is active");
                        root.stopRequested = true; S.Recording.stop();
                    } else if ((root.mode === "empty" || root.mode === "escape")) root.check(ok && result.cancelled && !S.Recording.recording,"Empty selector returns a cancelled result");
                    else root.check(!ok && error.length > 0 && !S.Recording.recording,"Selector/recorder failure returns an error");
                });
            }
            if (root.returned && !S.Recording.busy && !S.Recording.recording) {
                root.check(!root.nativeDialogOpen,"Callback releases native dialog ownership");
                console.info("CAPTURE_CONTROLLER_OK",root.mode); Qt.quit();
            }
        }
    }
}
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sumi-capture-controller-') as temporary:
        work = Path(temporary)
        shell = work / 'shell'
        shutil.copytree(repo / 'shell', shell)
        (shell / 'shell.qml').write_text(HARNESS)
        binaries = work / 'bin'
        binaries.mkdir()
        (binaries / 'slurp').write_text(SELECTOR)
        (binaries / 'slurp').chmod(0o755)
        source = work / 'recorder.c'
        source.write_text(RECORDER)
        subprocess.run(['cc',str(source),'-o',str(binaries / 'wf-recorder')],check=True,capture_output=True,timeout=15)
        controller = binaries / 'fixture-desktopctl'
        controller.write_text('#!' + sys.executable + '\n' + 'import sys,os\nfrom functools import partial\nsys.path.insert(0, ' + repr(str(repo / 'lib')) + ')\nfrom sumi import actions,cli\nif os.environ["SUMI_CAPTURE_TEST_MODE"] == "timeout": actions.select_region = partial(actions.select_region, timeout=.2)\nraise SystemExit(cli.main())\n')
        controller.chmod(0o755)
        for mode in ('success','empty','escape','failure','timeout'):
            home = work / mode
            runtime = home / 'runtime'
            runtime.mkdir(parents=True,mode=0o700)
            pidfile = home / 'fixture.pid'
            selector_pidfile = home / 'selector.pid'
            env = dict(os.environ, HOME=str(home), SUMI_HOME=str(home), SUMI_STATE_DIR=str(home / 'state'),
                       XDG_RUNTIME_DIR=str(runtime), SUMI_PREVIEW='', QT_QPA_PLATFORM='offscreen',
                       SUMI_DESKTOPCTL=str(controller), SUMI_CAPTURE_TEST_MODE=mode,
                       SUMI_CAPTURE_TEST_PID=str(pidfile), SUMI_CAPTURE_TEST_SELECTOR_PID=str(selector_pidfile), PATH=str(binaries)+os.pathsep+os.environ['PATH'])
            try:
                result = subprocess.run(['qs','-p',str(shell)],env=env,capture_output=True,text=True,timeout=10)
                output = result.stdout + result.stderr
                if result.returncode or 'CAPTURE_CONTROLLER_OK' not in output or any(error in output for error in ('TypeError:','ReferenceError:','Unable to assign [undefined]','Failed to load configuration')):
                    raise SystemExit(output)
                selector_pid = int(selector_pidfile.read_text())
                if Path(f'/proc/{selector_pid}').exists():
                    raise SystemExit('Owned selector remained after controller callback: ' + mode)
            finally:
                if selector_pidfile.exists():
                    selector_pid = int(selector_pidfile.read_text())
                    try:
                        arguments = Path(f'/proc/{selector_pid}/cmdline').read_bytes().split(b'\0')
                        if os.fsencode(binaries / 'slurp') in arguments:
                            os.kill(selector_pid,signal.SIGKILL)
                    except (FileNotFoundError,ProcessLookupError):
                        pass
                # Only our compiled fixture process can be cleaned up here.
                if pidfile.exists():
                    pid = int(pidfile.read_text())
                    try:
                        executable = Path(f'/proc/{pid}/exe').resolve(strict=True)
                        if executable == binaries / 'wf-recorder':
                            os.kill(pid,signal.SIGINT)
                    except (FileNotFoundError,ProcessLookupError):
                        pass
        print('PASS: real Desktop/ControllerRequest/Recording/Python callbacks; detached recorder does not hold stdout; empty/Escape/error/startup failure/owned-selector timeout all release handoff; no real screen capture')


if __name__ == '__main__':
    main()
