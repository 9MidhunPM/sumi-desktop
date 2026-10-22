#!/usr/bin/env python3
"""Check learned ranking and real durable history without touching user state."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


BACKEND = '''#!/usr/bin/env python3
import json
import os
import sys

if sys.argv[1:3] == ["action", "capture"]:
    print(json.dumps({"cancelled": True} if sys.argv[3] == "region" else {"path": "/fixture/capture.png"}))
elif sys.argv[1:3] == ["action", "fixture-failure"]:
    print("Fixture action failed", file=sys.stderr)
    sys.exit(1)
else:
    os.execv(os.environ["SUMI_REAL_DESKTOPCTL"], [os.environ["SUMI_REAL_DESKTOPCTL"]] + sys.argv[1:])
'''

HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "services" as S
import "services/LauncherRanking.js" as Ranking

ShellRoot {
    QtObject {
        id: fakeApp
        property var activeScreen: null
        property bool acceptPanels: false
        property int opens: 0
        property int closed: 0
        function open(name, screen) { opens++; return acceptPanels; }
        function close() { closed++; }
    }
    Window {
        id: win; visible: true; width: 800; height: 700
        Launcher { id: launcher; app: fakeApp }
        TestCase {
            when: win.visible
            name: "LauncherHistory"
            property double now: 2000000000
            function check(value, message) {
                if (!value) { console.error("LAUNCHER_HISTORY_FAILED", message); Qt.exit(1); throw new Error(message); }
            }
            function equal(actual, expected, message) {
                check(actual === expected, (message || "Values differ") + ": " + actual + " != " + expected);
            }
            function waitEqual(object, property, expected, timeout) {
                const deadline = Date.now() + (timeout || 4000);
                while (object[property] !== expected && Date.now() < deadline) wait(20);
                equal(object[property], expected, "Timed out waiting for " + property);
            }
            function entry(id, name, detail, priority) {
                return {historyId:id, name:name, detail:detail || "", coldPriority:priority || 0};
            }
            function usage(score, age, queries) {
                return {count:score, score:score, lastUsed:now-age, queries:queries || {}};
            }
            function ranked(list, query, entries) {
                return Ranking.rank(list, query, {version:1, entries:entries || {}}, now);
            }
            function ids(list) { return list.map(item => item.historyId).join(","); }
            function settleHistory() { tryCompare(S.LauncherHistory, "busy", false, 4000); }
            function settleAction() { tryCompare(S.Desktop, "pendingCount", 0, 4000); settleHistory(); }
            function test_01_relevance_and_defaults() {
                console.info("HISTORY_STAGE relevance");
                compare(Ranking.normalize("  YoU   Tube  "), "you tube");
                const list = [entry("app:metadata", "Alpha", "Your friendly browser"),
                              entry("app:firefox-youtube", "YouTube", "Firefox web app", 8),
                              entry("app:brave-youtube", "YouTube", "Brave web app", 7)];
                compare(ids(ranked(list, "you")), "app:brave-youtube,app:firefox-youtube,app:metadata");
                compare(ids(ranked(list, "missing")), "");
                const tiers = [entry("metadata", "Alpha", "you"), entry("substring", "Myoutube"),
                               entry("word", "Open YouTube"), entry("prefix", "YouTube"), entry("exact", "You")];
                compare(ids(ranked(tiers, "you")), "exact,prefix,word,substring,metadata");
                const known = {metadata:usage(100, 0, {you:usage(4, 0)})};
                compare(ids(ranked(tiers, "you", known)), "exact,metadata,prefix,word,substring");
                compare(ranked(tiers, "  YOU  ", known)[1].historyId, "metadata");
            }
            function test_02_frequency_decay_and_ties() {
                console.info("HISTORY_STAGE frequency");
                const list = [entry("a", "Alpha"), entry("b", "Beta"), entry("c", "Gamma")];
                compare(ids(ranked(list, "", {b:usage(4, 0)})), "b,a,c");
                compare(ids(ranked(list, "", {a:usage(10, 8*2592000), b:usage(2, 0)})), "b,a,c");
                compare(ids(ranked(list, "", {a:usage(2, 200), b:usage(2, 0)})), "b,a,c");
                const sameNames = [entry("b", "Same", "", 2), entry("a", "Same", "", 2)];
                compare(ids(ranked(sameNames, "")), "a,b");
                const queryList = [entry("a", "Alpha", "find things"), entry("b", "Finder")];
                const queryEntries = {a:usage(100, 0, {find:usage(1, 0)}), b:usage(1, 0, {find:usage(3, 0)})};
                compare(ids(ranked(queryList, "find", queryEntries)), "b,a");
                compare(ids(ranked(queryList, "find", {a:usage(100, 0, {find:usage(1, 20*2592000)})})), "b,a");
            }
            function test_03_serialized_record_reset() {
                console.info("HISTORY_STAGE queue");
                tryCompare(S.LauncherHistory, "loaded", true, 4000);
                S.LauncherHistory.record("app:discard", "one");
                S.LauncherHistory.record("app:discard", "two");
                S.LauncherHistory.reset();
                S.LauncherHistory.record("app:kept", "  KEEP   ME  ");
                settleHistory();
                compare(Object.keys(S.LauncherHistory.document.entries).join(","), "app:kept");
                compare(S.LauncherHistory.document.entries["app:kept"].count, 1);
                compare(S.LauncherHistory.document.entries["app:kept"].queries["keep me"].count, 1);
                S.LauncherHistory.reset();
                settleHistory();
                compare(Object.keys(S.LauncherHistory.document.entries).length, 0, "Reset clears current history");
            }
            function test_035_late_history_preserves_selection() {
                console.info("HISTORY_STAGE selection");
                launcher.tab = "Actions";
                launcher.smokeResults.currentIndex = 3;
                const selectedId = launcher.entries[launcher.smokeResults.currentIndex].historyId;
                const promotedId = launcher.entries[launcher.entries.length - 1].historyId;
                S.LauncherHistory.record(promotedId, "");
                settleHistory();
                wait(30);
                compare(launcher.entries[0].historyId, promotedId, "New usage reranks entries");
                compare(launcher.entries[launcher.smokeResults.currentIndex].historyId, selectedId, "Late memory preserves selected entry");
                S.LauncherHistory.reset();
                settleHistory();
                wait(30);
            }
            function test_04_action_acceptance_and_cancel() {
                console.info("HISTORY_STAGE action");
                launcher.tab = "Actions";
                const panel = launcher.actions.filter(item => item.panel === "settings")[0];
                verify(!!panel);
                launcher.activate(panel);
                settleHistory();
                compare(Object.keys(S.LauncherHistory.document.entries).length, 0, "Rejected panel never learns");
                fakeApp.acceptPanels = true;
                launcher.activate(panel);
                settleHistory();
                compare(S.LauncherHistory.document.entries["action:settings"].count, 1, "Accepted panel learns once");
                launcher.activate({name:"Cancelled capture", historyId:"action:capture-region", command:"capture", args:["region"]});
                settleAction();
                verify(!S.LauncherHistory.document.entries["action:capture-region"], "Cancelled capture never learns");
                launcher.activate({name:"Successful capture", historyId:"action:capture-annotate", command:"capture", args:["screen"]});
                settleAction();
                compare(S.LauncherHistory.document.entries["action:capture-annotate"].count, 1);
                launcher.activate({name:"Failed command", historyId:"action:lock", command:"fixture-failure", args:[]});
                settleAction();
                verify(!S.LauncherHistory.document.entries["action:lock"], "Failed command never learns");
                verify(launcher.error.length > 0);
                console.info("SUMI_LAUNCHER_HISTORY_OK");
                Qt.quit();
            }
        }
    }
}
'''

PREVIEW_HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "services" as S
ShellRoot {
    Window {
        id: win; visible: true; width: 200; height: 100
        TestCase {
            when: win.visible
            name: "LauncherHistoryPreview"
            function test_preview_does_not_learn() {
                tryCompare(S.LauncherHistory, "loaded", true, 4000);
                S.LauncherHistory.record("app:preview", "you");
                S.LauncherHistory.reset();
                wait(250);
                if (S.LauncherHistory.busy || S.LauncherHistory.document.entries["app:preview"]) {
                    console.error("LAUNCHER_PREVIEW_CHANGED_HISTORY"); Qt.exit(1); return;
                }
                console.info("SUMI_LAUNCHER_PREVIEW_OK");
                Qt.quit();
            }
        }
    }
}
'''


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-launcher-history-") as temporary:
        work = Path(temporary)
        config = work / "shell"
        shutil.copytree(repo / "shell", config)
        desktop = config / "services/Desktop.qml"
        desktop.write_text(desktop.read_text().replace(
            'readonly property bool preview: Quickshell.env("SUMI_PREVIEW") === "1"',
            'readonly property bool preview: false'))
        launcher = config / "Launcher.qml"
        launcher.write_text(launcher.read_text().replace(
            "    property string initialTab:",
            "    readonly property var smokeResults: results\n    property string initialTab:", 1))
        (config / "shell.qml").write_text(HARNESS.replace("compare(", "equal(").replace("verify(", "check(").replace("tryCompare(", "waitEqual("))
        backend = work / "backend"
        backend.write_text(BACKEND)
        backend.chmod(0o755)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, SUMI_PREVIEW="1", SUMI_DESKTOPCTL=str(backend),
                           SUMI_REAL_DESKTOPCTL=str(repo / "bin/desktopctl"),
                           SUMI_HOME=str(work), SUMI_STATE_DIR=str(work / "state"), HOME=str(work),
                           XDG_RUNTIME_DIR=str(runtime), QT_QPA_PLATFORM="offscreen",
                           XDG_DATA_HOME=str(work / "data"), XDG_DATA_DIRS=str(work / "empty-data"),
                           XDG_CONFIG_HOME=str(work / "xdg-config"), XDG_CACHE_HOME=str(work / "cache"),
                           DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(work / "absent-bus"))
        result = subprocess.run(["qs", "-p", str(config), "-n"], env=environment,
                                capture_output=True, text=True, timeout=20)
        output = result.stdout + result.stderr
        failures = ("TypeError:", "ReferenceError:", "Failed to load configuration", "Unable to assign [undefined]")
        if result.returncode or "SUMI_LAUNCHER_HISTORY_OK" not in output or any(message in output for message in failures):
            raise SystemExit(output)
        history = json.loads((work / "state/launcher-history.json").read_text())
        if {key: value["count"] for key, value in history["entries"].items()} != {"action:settings": 1, "action:capture-annotate": 1}:
            raise SystemExit("Unexpected activation history: " + json.dumps(history))
        desktop.write_text((repo / "shell/services/Desktop.qml").read_text())
        (config / "shell.qml").write_text(PREVIEW_HARNESS)
        preview = subprocess.run(["qs", "-p", str(config), "-n"], env=environment,
                                 capture_output=True, text=True, timeout=15)
        preview_output = preview.stdout + preview.stderr
        if preview.returncode or "SUMI_LAUNCHER_PREVIEW_OK" not in preview_output:
            raise SystemExit(preview_output)
        if json.loads((work / "state/launcher-history.json").read_text()) != history:
            raise SystemExit("Preview wrote or reset real launcher history")
        print("PASS: relevance tiers; query memory; frequency/decay/ties; queued record/reset; accepted panels; cancelled captures; failed actions")


if __name__ == "__main__":
    main()
