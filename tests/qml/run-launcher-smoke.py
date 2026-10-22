#!/usr/bin/env python3
"""Exercise launcher races and clipboard controls against an isolated backend."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


BACKEND = '''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
import time

with open(os.environ["SUMI_TEST_ACTION_LOG"], "a") as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[1:3] == ["action", "search-files"]:
    query = sys.argv[3]
    time.sleep(.6 if query == "old" else .03)
    print(json.dumps([{"name": query, "detail": query, "path": str(Path(os.environ["SUMI_TEST_WORK"]) / query)}]))
elif sys.argv[1:3] == ["action", "clipboard"] and sys.argv[3] in {"status", "pause", "resume"}:
    state = Path(os.environ["SUMI_TEST_WORK"]) / "clipboard-paused"
    paused = state.read_text() == "true" if state.exists() else True
    if sys.argv[3] != "status":
        time.sleep(.15)
        paused = sys.argv[3] == "pause"
        state.write_text("true" if paused else "false")
    print(json.dumps({"paused": paused, "healthy": True}))
elif sys.argv[1:] == ["action", "clipboard", "delete", "fail"]:
    print("Deletion failed", file=sys.stderr)
    sys.exit(1)
elif sys.argv[1:] == ["action", "clipboard", "list"]:
    state = Path(os.environ["SUMI_TEST_WORK"]) / "clipboard-entries"
    entries = json.loads(state.read_text()) if state.exists() else [{"id": "1", "name": "One", "detail": "Clipboard"}, {"id": "2", "name": "Two", "detail": "Clipboard"}]
    time.sleep(.35)
    print(json.dumps(entries))
elif sys.argv[1:4] == ["action", "clipboard", "delete"] or sys.argv[1:] == ["action", "clipboard", "clear"]:
    state = Path(os.environ["SUMI_TEST_WORK"]) / "clipboard-entries"
    entries = json.loads(state.read_text()) if state.exists() else [{"id": "1", "name": "One", "detail": "Clipboard"}, {"id": "2", "name": "Two", "detail": "Clipboard"}]
    entries = [] if sys.argv[3] == "clear" else [entry for entry in entries if entry["id"] != sys.argv[4]]
    state.write_text(json.dumps(entries))
    print("{}")
else:
    print("[]")
'''

HARNESS = '''import QtQuick
import Quickshell

ShellRoot {
    id: smoke
    QtObject { id: fakeApp; property var activeScreen: null; function open(name, screen) {} function close() {} }
    Window { visible: true; width: 800; height: 700; Launcher { id: launcher; app: fakeApp } }
    property string phase: "apps"
    property double phaseStarted: Date.now()
    function fail(message) { console.error(message); Qt.exit(1); }
    Timer {
        interval: 100
        repeat: true
        running: true
        onTriggered: {
            const elapsed = Date.now() - smoke.phaseStarted;
            if (elapsed > 5000) { smoke.fail("LAUNCHER_PHASE_TIMEOUT " + smoke.phase); return; }
            if (smoke.phase === "apps") {
                const availableApps = DesktopEntries.applications.values.filter(entry => !entry.noDisplay && !entry.id.startsWith("theme-switcher-"));
                if (launcher.entries.length !== availableApps.length) { smoke.fail("APPS_HIDDEN"); return; }
                if (launcher.entries.some(entry => entry.entry.id.startsWith("theme-switcher-"))) { smoke.fail("LEGACY_THEME_ACTION_EXPOSED"); return; }
                const favorites = ["Kitty", "Thunar", "Brave", "Antigravity", "Papers", "Loupe", "Ghostty", "Other"];
                for (let index = 0; index < favorites.length; index++) {
                    if (launcher.appPriority({name: favorites[index]}) !== index) { smoke.fail("FAVORITE_ORDER"); return; }
                }
                launcher.smokeSearch = "old";
                launcher.tab = "Files";
                smoke.phase = "old-query";
                smoke.phaseStarted = Date.now();
            } else if (smoke.phase === "old-query" && elapsed >= 150) {
                launcher.smokeSearch = "new";
                launcher.refresh();
                smoke.phase = "new-query";
                smoke.phaseStarted = Date.now();
            } else if (smoke.phase === "new-query" && launcher.fetched.length > 0) {
                if (launcher.fetched.length !== 1 || launcher.fetched[0].name !== "new") { smoke.fail("STALE_FILE_RESULT"); return; }
                launcher.smokeSearch = "";
                launcher.tab = "Clipboard";
                smoke.phase = "clipboard";
                smoke.phaseStarted = Date.now();
            } else if (smoke.phase === "clipboard" && launcher.clipboardPaused && launcher.fetched.length === 2) {
                launcher.toggleClipboard();
                if (!launcher.clipboardPaused || !launcher.clipboardBusy) { smoke.fail("OPTIMISTIC_CLIPBOARD_RESUME"); return; }
                smoke.phase = "resuming";
                smoke.phaseStarted = Date.now();
            } else if (smoke.phase === "resuming" && !launcher.clipboardBusy) {
                if (launcher.clipboardPaused) { smoke.fail("CLIPBOARD_RESUME"); return; }
                launcher.toggleClipboard();
                if (launcher.clipboardPaused) { smoke.fail("OPTIMISTIC_CLIPBOARD_PAUSE"); return; }
                smoke.phase = "pausing";
                smoke.phaseStarted = Date.now();
            } else if (smoke.phase === "pausing" && !launcher.clipboardBusy) {
                if (!launcher.clipboardPaused) { smoke.fail("CLIPBOARD_PAUSE"); return; }
                launcher.refresh();
                smoke.phase = "failure-list-inflight";
                smoke.phaseStarted = Date.now();
            } else if (smoke.phase === "failure-list-inflight" && elapsed > 100) {
                launcher.deleteClipboard("fail");
                smoke.phase = "delete-failure";
                smoke.phaseStarted = Date.now();
            } else if (smoke.phase === "delete-failure" && !launcher.clipboardBusy && launcher.fetched.length === 2) {
                if (launcher.fetched.length !== 2 || !launcher.error.length) { smoke.fail("FAILED_DELETE_HIDDEN"); return; }
                launcher.deleteClipboard("1");
                if (launcher.fetched.length !== 2) { smoke.fail("OPTIMISTIC_DELETE"); return; }
                smoke.phase = "deleting";
                smoke.phaseStarted = Date.now();
            } else if (smoke.phase === "deleting" && !launcher.clipboardBusy) {
                if (launcher.fetched.length !== 1 || launcher.fetched[0].id !== "2") { smoke.fail("CLIPBOARD_DELETE"); return; }
                launcher.activeRequestKey = launcher.currentRequestKey();
                launcher.smokeFetcher.command = [Quickshell.env("SUMI_DESKTOPCTL"), "action", "clipboard", "list"];
                launcher.smokeFetcher.running = true;
                smoke.phase = "list-inflight";
                smoke.phaseStarted = Date.now();
            } else if (smoke.phase === "list-inflight" && elapsed > 100) {
                launcher.clearClipboard();
                if (launcher.fetched.length !== 1) { smoke.fail("OPTIMISTIC_CLEAR"); return; }
                smoke.phase = "clearing";
                smoke.phaseStarted = Date.now();
            } else if (smoke.phase === "clearing" && !launcher.clipboardBusy) {
                if (launcher.fetched.length !== 0) { smoke.fail("CLIPBOARD_CLEAR"); return; }
                smoke.phase = "cleared-stable";
                smoke.phaseStarted = Date.now();
            } else if (smoke.phase === "cleared-stable" && elapsed > 900) {
                if (launcher.fetched.length !== 0) { smoke.fail("STALE_CLIPBOARD_LIST_RESTORED"); return; }
                console.info("SUMI_LAUNCHER_REGRESSION_OK");
                Qt.quit();
            }
        }
    }
}
'''


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-launcher-smoke-") as temporary:
        work = Path(temporary)
        config = work / "shell"
        shutil.copytree(repo / "shell", config)
        # Only this temporary copy permits actions, all against the fixture below.
        desktop = config / "services/Desktop.qml"
        desktop.write_text(desktop.read_text().replace('readonly property bool preview: Quickshell.env("SUMI_PREVIEW") === "1"', 'readonly property bool preview: false'))
        launcher = config / "Launcher.qml"
        launcher.write_text(launcher.read_text().replace(
            "    property string initialTab:",
            "    property alias smokeSearch: search.text\n    readonly property var smokeFetcher: fetcher\n    property string initialTab:",
            1,
        ))
        backend = work / "backend"
        backend.write_text(BACKEND)
        backend.chmod(0o755)
        (config / "shell.qml").write_text(HARNESS)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        action_log = work / "actions.jsonl"
        environment = dict(
            os.environ,
            SUMI_PREVIEW="1",
            SUMI_DESKTOPCTL=str(backend),
            SUMI_TEST_WORK=str(work),
            SUMI_TEST_ACTION_LOG=str(action_log),
            SUMI_STATE_DIR=str(work / "state"),
            XDG_RUNTIME_DIR=str(runtime),
            QT_QPA_PLATFORM="offscreen",
        )
        result = subprocess.run(["qs", "-p", str(config)], env=environment, capture_output=True, text=True, timeout=20)
        output = result.stdout + result.stderr
        failures = ("TypeError:", "ReferenceError:", "Failed to load configuration", "Unable to assign [undefined]")
        if result.returncode or "SUMI_LAUNCHER_REGRESSION_OK" not in output or any(message in output for message in failures):
            raise SystemExit(output)
        actions = [json.loads(line) for line in action_log.read_text().splitlines()]
        old_request = ["action", "search-files", "old"]
        new_request = ["action", "search-files", "new"]
        if old_request not in actions or new_request not in actions or actions.index(old_request) >= actions.index(new_request):
            raise SystemExit(f"The delayed request and replacement were not exercised: {actions}")
        print("PASS: stale file results discarded; latest query queued; clipboard status/pause/resume/delete/clear; complete app list and favorite order")


if __name__ == "__main__":
    main()
