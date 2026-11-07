#!/usr/bin/env python3
"""Exercise metric validation and real demand-gated process lifetime in isolation."""
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
import "services" as S
ShellRoot {
    property int starts: 0
    Connections { target: S.SystemStats; function onObservingChanged() { if (S.SystemStats.observing) starts++; } }
    TestCase {
        name: "SystemStats"
        when: true
        function check(value, message) { if (!value) { console.error("SYSTEM_STATS_FAILED", message); Qt.exit(1); throw new Error(message); } }
        function sample(overrides = {}) {
            return JSON.stringify(Object.assign({cpuAvailable:true, cpuPercent:44, memoryAvailable:true, memoryUsed:512, memoryTotal:1024,
                storageAvailable:true, storageUsed:300, storageTotal:1000, storageFree:700, error:""}, overrides));
        }
        function test_metrics() {
            const one = S.SystemStats.createConsumer(), two = S.SystemStats.createConsumer();
            wait(50);
            check(!S.SystemStats.active && !S.SystemStats.observing && starts === 0 && !S.SystemStats.ready, "No demand does no process work");
            S.SystemStats.setDemand(99999, true);
            check(!S.SystemStats.active, "Unknown consumer cannot start observer");
            S.SystemStats.setDemand(one, true);
            check(!S.SystemStats.active && !S.SystemStats.ready && starts === 0, "Preview never starts hardware observation or fakes values");
            S.Desktop.preview = false;
            let elapsed = 0;
            while (!S.SystemStats.ready && elapsed < 2500) { wait(20); elapsed += 20; }
            check(S.SystemStats.active && S.SystemStats.observing && S.SystemStats.ready && starts === 1, "First real demand starts one shared stream");
            check(S.SystemStats.cpuPercent === 44 && S.SystemStats.memoryPercent === 50 && S.SystemStats.storagePercent === 30 && S.SystemStats.storageFree === 700, "Observed byte values and percentages agree");
            S.SystemStats.setDemand(two, true);
            S.SystemStats.setDemand(one, false); wait(70);
            check(S.SystemStats.observing && starts === 1 && S.SystemStats.ready, "Second consumer shares the process and keeps it alive");
            S.SystemStats.observedLine(sample({cpuAvailable:false,cpuPercent:null,error:"CPU needs a fresh sample."}));
            check(!S.SystemStats.ready && !S.SystemStats.cpuAvailable && S.SystemStats.cpuPercent === 0 && S.SystemStats.memoryAvailable, "Missing CPU clears stale CPU while retaining truthful partial observations");
            S.SystemStats.observedLine(sample({memoryUsed:2048, storageUsed:-1}));
            check(!S.SystemStats.memoryAvailable && !S.SystemStats.storageAvailable && S.SystemStats.memoryUsed === 0 && S.SystemStats.storagePercent === 0, "Invalid memory and storage never create plausible percentages");
            S.SystemStats.observedLine("{invalid");
            check(!S.SystemStats.ready && !S.SystemStats.cpuAvailable && S.SystemStats.error.length > 0, "Malformed stream clears availability");
            S.SystemStats.observedLine(sample());
            check(S.SystemStats.ready && S.SystemStats.error === "", "A fresh valid observation recovers all metrics");
            S.SystemStats.releaseConsumer(two); wait(140);
            check(!S.SystemStats.active && !S.SystemStats.observing && !S.SystemStats.ready && S.SystemStats.cpuPercent === 0, "Last visible consumer disappearing stops work and clears stale values");
            S.SystemStats.setDemand(two, true);
            check(!S.SystemStats.active, "Released IDs cannot resurrect demand");
            S.SystemStats.setDemand(one, true);
            elapsed = 0;
            while (!S.SystemStats.ready && elapsed < 2500) { wait(20); elapsed += 20; }
            check(S.SystemStats.ready && starts === 2, "Returning to visible controls starts one fresh baseline");
            S.Desktop.preview = true; wait(120);
            check(!S.SystemStats.active && !S.SystemStats.observing && !S.SystemStats.ready, "Entering preview stops an existing observer");
            S.SystemStats.observedLine(sample());
            check(!S.SystemStats.ready && S.SystemStats.cpuPercent === 0, "Late lines cannot repopulate hidden or preview values");
            S.SystemStats.releaseConsumer(one);
            console.info("SYSTEM_STATS_OK"); Qt.quit();
        }
    }
}
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-system-stats-") as temporary:
        work = Path(temporary)
        services = work / "services"
        services.mkdir()
        shutil.copy2(repo / "shell/services/SystemStats.qml", services)
        log = work / "lifecycle.jsonl"
        controller = work / "controller"
        controller.write_text(f'''#!{sys.executable}
import json, os, signal, sys, time
from pathlib import Path
log = Path({str(log)!r})
def record(value):
    with log.open("a") as output: output.write(json.dumps(value) + "\\n")
def stop(*_):
    record({{"event":"stop"}})
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
record({{"event":"start", "args":sys.argv[1:]}})
if os.environ.get("STATS_FIXTURE_EXIT") == "1": sys.exit(1)
time.sleep(.2)
print(json.dumps({{"cpuAvailable":True,"cpuPercent":44,"memoryAvailable":True,"memoryUsed":512,"memoryTotal":1024,"storageAvailable":True,"storageUsed":300,"storageTotal":1000,"storageFree":700,"error":""}}),flush=True)
while True: time.sleep(1)
''')
        controller.chmod(0o700)
        (services / "Desktop.qml").write_text("pragma Singleton\nimport QtQuick\nimport Quickshell\nSingleton { property bool preview: true; readonly property string controller: " + json.dumps(str(controller)) + " }\n")
        (services / "qmldir").write_text("singleton SystemStats SystemStats.qml\nsingleton Desktop Desktop.qml\n")
        (work / "shell.qml").write_text(HARNESS)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime), SUMI_PREVIEW="0")
        result = subprocess.run(["qs", "-p", str(work)], env=environment, text=True, capture_output=True, timeout=12)
        output = result.stdout + result.stderr
        errors = ("TypeError:", "ReferenceError:", "Unable to assign [undefined]", "Failed to load configuration", "FAIL!", "Binding loop")
        if result.returncode or "SYSTEM_STATS_OK" not in output or any(error in output for error in errors):
            raise SystemExit(output)
        events = [json.loads(line) for line in log.read_text().splitlines()]
        starts = [entry for entry in events if entry["event"] == "start"]
        stops = [entry for entry in events if entry["event"] == "stop"]
        if len(starts) != 2 or len(stops) != 2 or any(entry["args"] != ["action", "system-stats-watch"] for entry in starts):
            raise SystemExit(f"Incorrect observer process lifecycle: {events}")
        print("PASS: real shared observer starts/stops with visible demand; preview isolation; byte percentages; partial and malformed availability; stale-line rejection")
        log.write_text("")
        (work / "shell.qml").write_text('''import QtQuick
import QtTest
import Quickshell
import "services" as S
ShellRoot {
    TestCase {
        when: true
        function test_bounded_retry() {
            S.Desktop.preview = false;
            const consumer = S.SystemStats.createConsumer(); S.SystemStats.setDemand(consumer, true);
            wait(8200);
            if (S.SystemStats.retryCount !== 3 || S.SystemStats.observing || S.SystemStats.ready || !S.SystemStats.error) {
                console.error("SYSTEM_STATS_RETRY_FAILED", S.SystemStats.retryCount, S.SystemStats.observing, S.SystemStats.error); Qt.exit(1); return;
            }
            S.SystemStats.releaseConsumer(consumer);
            console.info("SYSTEM_STATS_RETRY_OK"); Qt.quit();
        }
    }
}
''')
        retry_environment = dict(environment, STATS_FIXTURE_EXIT="1")
        result = subprocess.run(["qs", "-p", str(work)], env=retry_environment, text=True, capture_output=True, timeout=12)
        output = result.stdout + result.stderr
        if result.returncode or "SYSTEM_STATS_RETRY_OK" not in output or any(error in output for error in errors):
            raise SystemExit(output)
        attempts = [json.loads(line) for line in log.read_text().splitlines()]
        if len(attempts) != 4:
            raise SystemExit(f"Observer retry was not bounded: {attempts}")
        print("PASS: failed observer retries only three times and remains unavailable after exhaustion")


if __name__ == "__main__":
    main()
