#!/usr/bin/env python3
"""Exercise controller receipts and failure cleanup without live desktop actions."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile


BACKEND = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
import time

root = Path(__file__).parent
mode = os.environ["SUMI_TEST_MODE"]
with (root / "pids").open("a") as output:
    output.write(str(os.getpid()) + "\n")
if sys.argv[1:4] == ["operation", "status", "latest"]:
    (root / "latest-probe").write_text("requested")
    if mode not in {"resumed-success", "resumed-failure"}:
        raise SystemExit(3)
    print(json.dumps({"operation_id": "a" * 32,
                      "status": "queued" if mode == "resumed-success" else "running"}))
    raise SystemExit(0)
if sys.argv[1:3] == ["operation", "status"]:
    counter = root / "poll-count"
    count = int(counter.read_text()) + 1 if counter.exists() else 1
    counter.write_text(str(count))
    if mode == "hung-status":
        time.sleep(20)
    state = "queued" if count == 1 and not mode.startswith("resumed-") else "running"
    if count >= 3 and mode in {"success", "failure", "resumed-success", "resumed-failure"}:
        state = "succeeded" if mode in {"success", "resumed-success"} else "failed"
    print(json.dumps({"operation_id": "a" * 32, "status": state,
                      "result": {"value": "complete"}, "error": "Synthetic transition failure"}))
elif mode == "callback-error":
    print(json.dumps({"value": "complete"}))
elif mode == "hung-initial":
    time.sleep(20)
else:
    (root / "initial-command").write_text("requested")
    print(json.dumps({"scheduled": True, "operation_id": "a" * 32, "status": "queued"}))
'''


HARNESS = '''import QtQuick
import Quickshell
import "services" as S

ShellRoot {
    id: smoke
    property string mode: Quickshell.env("SUMI_TEST_MODE")
    readonly property bool resumed: mode.indexOf("resumed-") === 0
    property int callbacks: 0
    property int completions: 0
    property bool resultOk: false
    property string resultError: ""
    property var resultValue: ({})
    property QtObject throwingRequest: null

    function check(condition, message) {
        if (!condition) {
            console.error("SUMI_CONTROLLER_FAILED", mode, message);
            Qt.exit(1);
        }
    }
    Component { id: directFactory; S.ControllerRequest { timeoutMs: 1800 } }
    Connections {
        target: S.Desktop
        function onCompleted(action, ok, result, error) {
            smoke.completions += 1;
            if (smoke.resumed) {
                smoke.check(action === "desktop change", "resumed receipt has unexpected action label");
                smoke.resultOk = ok;
                smoke.resultValue = result;
                smoke.resultError = error;
                settlement.start();
            }
        }
    }
    Component.onCompleted: {
        if (resumed) {
            // Importing Desktop owns startup recovery. No new request or UI
            // callback is necessary to complete the pre-existing receipt.
        } else if (mode === "callback-error") {
            throwingRequest = directFactory.createObject(smoke, {
                argv: [], label: "callback cleanup",
                callback: function(ok, result, error) {
                    smoke.callbacks += 1;
                    smoke.resultOk = ok;
                    settlement.start();
                    throw new Error("Expected synthetic callback exception");
                }
            });
            throwingRequest.finished.connect(function(ok, result, error) { smoke.completions += 1; });
            throwingRequest.start();
        } else {
            S.Desktop.run(["test"], mode, function(ok, result, error) {
                smoke.callbacks += 1;
                smoke.resultOk = ok;
                smoke.resultValue = result;
                smoke.resultError = error;
                settlement.start();
            });
            smoke.check(S.Desktop.pendingCount === 1, "request was not counted as pending");
        }
    }
    Timer {
        interval: 500
        running: smoke.resumed || ["success", "failure", "scheduled-only"].indexOf(smoke.mode) >= 0
        onTriggered: smoke.check(smoke.callbacks === 0 && smoke.completions === 0 && S.Desktop.pendingCount === 1,
                                "scheduled or queued receipt was reported as completion")
    }
    Timer {
        id: settlement
        interval: 180
        onTriggered: {
            smoke.check(smoke.callbacks === (smoke.resumed ? 0 : 1), "unexpected callback count");
            smoke.check(smoke.completions === 1, "completed signal did not fire exactly once");
            smoke.check(S.Desktop.pendingCount === 0, "pending count leaked after completion");
            if (smoke.mode === "callback-error") {
                smoke.check(smoke.resultOk, "direct request unexpectedly failed");
                smoke.check(smoke.throwingRequest === null, "throwing callback prevented request destruction");
            } else if (smoke.mode === "success" || smoke.mode === "resumed-success") {
                smoke.check(smoke.resultOk && smoke.resultValue.value === "complete",
                            "final receipt result was not returned");
                smoke.check(S.Desktop.lastError === "", "successful request retained an error");
            } else {
                smoke.check(!smoke.resultOk && smoke.resultError.length > 0,
                            "failed or pending operation was reported as success");
                smoke.check(S.Desktop.lastError === smoke.resultError, "failure was not exposed globally");
                if (smoke.mode === "failure" || smoke.mode === "resumed-failure")
                    smoke.check(smoke.resultError === "Synthetic transition failure", "final operation error was lost");
            }
            console.info("SUMI_CONTROLLER_OK", smoke.mode);
            Qt.quit();
        }
    }
    Timer { interval: 5000; running: true; onTriggered: { console.error("SUMI_CONTROLLER_FAILED", smoke.mode, "watchdog never completed request"); Qt.exit(1); } }
}
'''


def backend_processes(work: Path, backend: Path) -> list[int]:
    """Inspect only PIDs written by this test backend, guarding against PID reuse."""
    pids = []
    if (work / "pids").exists():
        for value in (work / "pids").read_text().splitlines():
            try:
                pid = int(value)
                command = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
                if os.fsencode(backend) in command:
                    pids.append(pid)
            except (FileNotFoundError, ProcessLookupError):
                pass
    return pids


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    modes = ("success", "failure", "scheduled-only", "missing", "hung-initial", "hung-status", "callback-error",
             "resumed-success", "resumed-failure")
    for mode in modes:
        with tempfile.TemporaryDirectory(prefix=f"sumi-controller-{mode}-") as temporary:
            work = Path(temporary)
            config = work / "shell"
            services = config / "services"
            services.mkdir(parents=True)
            for name in ("Desktop.qml", "ControllerRequest.qml"):
                shutil.copy2(repo / "shell/services" / name, services / name)
            # Inject only a shorter deadline into the same request factory used
            # by production. The controller and lifecycle code remain intact.
            desktop = services / "Desktop.qml"
            source = desktop.read_text()
            old = "ControllerRequest {}"
            if old not in source:
                raise SystemExit("Controller smoke timeout injection needs updating")
            desktop.write_text(source.replace(old, "ControllerRequest { timeoutMs: 1800 }", 1))
            (services / "qmldir").write_text("singleton Desktop Desktop.qml\nControllerRequest ControllerRequest.qml\n")
            (config / "shell.qml").write_text(HARNESS)
            runtime = work / "runtime"
            runtime.mkdir(mode=0o700)
            backend = work / "backend.py"
            backend.write_text(BACKEND)
            backend.chmod(0o700)
            environment = dict(os.environ, SUMI_PREVIEW="0", SUMI_TEST_MODE=mode,
                               SUMI_DESKTOPCTL=str(work / "missing" if mode == "missing" else backend),
                               SUMI_STATE_DIR=str(work / "state"), SUMI_DATA_DIR=str(work / "data"),
                               QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime),
                               DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent")
            try:
                result = subprocess.run(["qs", "-p", str(config)], env=environment,
                                        capture_output=True, text=True, timeout=8)
                output = result.stdout + result.stderr
                if result.returncode or f"SUMI_CONTROLLER_OK {mode}" not in output or "SUMI_CONTROLLER_FAILED" in output:
                    raise SystemExit(output)
                survivors = backend_processes(work, backend)
                if survivors:
                    raise SystemExit(f"Controller {mode} left a test backend running: {survivors}\n{output}")
                if mode.startswith("resumed-"):
                    if not (work / "latest-probe").exists() or (work / "initial-command").exists():
                        raise SystemExit(f"Controller {mode} did not resume its receipt without starting a new command\n{output}")
                    if int((work / "poll-count").read_text()) != 3:
                        raise SystemExit(f"Controller {mode} watched the same receipt more than once\n{output}")
                print(f"PASS: controller {mode}; exactly one result; cleanup complete")
            finally:
                # Kill only a positively identified synthetic child if a failing
                # regression leaves one behind; never inspect unrelated commands.
                for pid in backend_processes(work, backend):
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass


if __name__ == "__main__":
    main()
