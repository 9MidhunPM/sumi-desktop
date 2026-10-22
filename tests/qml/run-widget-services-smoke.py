#!/usr/bin/env python3
"""Exercise widget storage and Spotify policy with isolated native QML processes."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import threading


DESKTOP = '''pragma Singleton
import QtQuick
import Quickshell
Singleton {
    property bool preview: Quickshell.env("SUMI_PREVIEW") === "1"
    readonly property string controller: Quickshell.env("SUMI_DESKTOPCTL")
    property int actions: 0
    function action(command, arguments, callback) { actions += 1; }
}
'''

THEME = '''pragma Singleton
import QtQuick
import Quickshell
Singleton {
    readonly property string stateDir: Quickshell.env("SUMI_STATE_DIR")
    readonly property string wallpaper: "/synthetic/wallpaper.jpg"
    readonly property var document: ({imageKey: "synthetic-image", sourceSize: [1920, 1080]})
}
'''

STORAGE_HARNESS = '''import QtQuick
import Quickshell
import Quickshell.Io
import "services" as S

ShellRoot {
    id: smoke
    property string mode: Quickshell.env("SUMI_TEST_MODE")
    property int phase: 0
    property int savedCount: 0
    property bool gateReady: false
    function check(condition, message) {
        if (!condition) { console.error("SUMI_WIDGET_SERVICES_FAILED", mode, message); Qt.exit(1); }
    }
    function candidate(text) {
        const value = S.Widgets.defaults();
        value.priorities[0].text = text;
        value.enabled.deadline = false;
        value.deadline = {title: "Synthetic deadline", at: 1800000000000};
        value.layouts["synthetic-image"] = "right";
        return value;
    }
    Connections {
        target: S.Widgets
        function onSaved(ok) {
            smoke.savedCount += 1;
            if (smoke.mode === "retry" && smoke.phase === 1) {
                smoke.check(!ok && S.Widgets.error.length > 0, "failed storage write was reported as saved");
                smoke.check(S.Widgets.document.priorities[0].text === "Retry content", "failed save discarded current edit");
                smoke.phase = 2;
                console.info("SUMI_WIDGET_RETRY_READY");
            } else if (smoke.mode === "retry" && smoke.phase === 3) {
                smoke.check(ok && S.Widgets.error === "", "retry did not recover failed save");
                smoke.check(smoke.savedCount === 2, "retry emitted unexpected receipts");
                console.info("SUMI_WIDGET_SERVICES_OK", smoke.mode);
                Qt.quit();
            } else if (smoke.mode === "persist" && smoke.phase === 1) {
                smoke.check(ok && smoke.savedCount === 1, "coalesced saves did not settle once");
                smoke.check(S.Widgets.document.priorities[0].text === "Final edit", "older save replaced queued edit");
                Qt.callLater(function() {
                    smoke.check(!S.Widgets.saving && S.Widgets.error === "", "coalesced save remained pending");
                    smoke.phase = 2;
                    console.info("SUMI_WIDGET_COALESCED");
                });
            } else {
                smoke.check(false, "unexpected save receipt in phase " + smoke.phase);
            }
        }
    }
    FileView {
        path: Quickshell.env("SUMI_STATE_DIR") + "/gate.json"
        preload: true
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: { try { smoke.gateReady = JSON.parse(text()).ready === true; } catch (error) {} }
    }
    Timer {
        interval: 30
        repeat: true
        running: true
        onTriggered: {
            if (smoke.phase === 0 && S.Widgets.loaded) {
                smoke.check(S.Widgets.document.priorities[0].text === "", "missing-file default was not empty");
                smoke.phase = 1;
                if (smoke.mode === "preview") {
                    smoke.check(!S.Widgets.saveDocument(smoke.candidate("Preview edit")), "preview accepted save");
                    S.Widgets.retrySave();
                    S.Widgets.setLayout("split");
                    S.Widgets.togglePriority(0);
                    smoke.check(S.Widgets.document.priorities[0].text === "" && !S.Widgets.saving,
                                "preview mutated widget document");
                    previewSettled.start();
                } else if (smoke.mode === "retry") {
                    smoke.check(S.Widgets.saveDocument(smoke.candidate("Retry content")), "retry candidate rejected");
                } else {
                    smoke.check(S.Widgets.saveDocument(smoke.candidate("First edit")), "initial candidate rejected");
                    smoke.check(S.Widgets.saveDocument(smoke.candidate("Middle edit")), "middle candidate rejected");
                    smoke.check(S.Widgets.saveDocument(smoke.candidate("Final edit")), "final candidate rejected");
                    smoke.check(S.Widgets.savePending, "edits were not queued behind a running native save");
                }
            } else if (smoke.mode === "retry" && smoke.phase === 2 && smoke.gateReady) {
                smoke.phase = 3;
                S.Widgets.retrySave();
            } else if (smoke.mode === "persist" && smoke.phase === 2 && S.Widgets.error.length > 0) {
                smoke.check(S.Widgets.document.priorities[0].text === "Final edit", "malformed JSON replaced valid document");
                smoke.phase = 3;
                console.info("SUMI_WIDGET_WRITE_SCHEMA_INVALID");
            } else if (smoke.mode === "persist" && smoke.phase === 3 && smoke.gateReady) {
                schemaSettled.start();
                smoke.phase = 4;
            } else if (smoke.mode === "persist" && smoke.phase === 5 && S.Widgets.document.priorities[0].text === "External edit") {
                smoke.check(S.Widgets.error === "", "valid external replacement retained old error");
                smoke.check(S.Widgets.layoutMode === "right", "image-specific layout was not restored");
                console.info("SUMI_WIDGET_SERVICES_OK", smoke.mode);
                Qt.quit();
            }
        }
    }
    Timer {
        id: schemaSettled
        interval: 150
        onTriggered: {
            smoke.check(S.Widgets.document.priorities[0].text === "Final edit", "invalid schema replaced valid document");
            smoke.check(S.Widgets.error.length > 0, "invalid schema was not surfaced");
            smoke.phase = 5;
            console.info("SUMI_WIDGET_WRITE_VALID");
        }
    }
    Timer {
        id: previewSettled
        interval: 400
        onTriggered: {
            smoke.check(smoke.savedCount === 0 && !S.Widgets.saving, "preview started a storage process");
            console.info("SUMI_WIDGET_SERVICES_OK", smoke.mode);
            Qt.quit();
        }
    }
    Timer { interval: 8000; running: true; onTriggered: { console.error("SUMI_WIDGET_SERVICES_FAILED", smoke.mode, "timeout in phase", smoke.phase); Qt.exit(1); } }
}
'''

MEDIA_HARNESS = '''import QtQuick
import Quickshell
import "services" as S

ShellRoot {
    id: smoke
    function check(condition, message) {
        if (!condition) { console.error("SUMI_WIDGET_SERVICES_FAILED", "media", message); Qt.exit(1); }
    }
    component FakePlayer: QtObject {
        property string dbusName: ""
        property string desktopEntry: ""
        property string identity: "Spotify"
        property string trackTitle: "Synthetic track"
        property string trackArtist: "Synthetic artist"
        property string trackArtUrl: "file:///synthetic/art.jpg"
        property bool isPlaying: false
        property bool lengthSupported: true
        property bool positionSupported: true
        property real length: 240
        property real position: 24
        property bool canGoPrevious: true
        property bool canTogglePlaying: true
        property bool canGoNext: true
        property bool canRaise: true
        property int previousCount: 0
        property int toggleCount: 0
        property int nextCount: 0
        property int raiseCount: 0
        signal trackChanged()
        function previous() { previousCount += 1; }
        function togglePlaying() { toggleCount += 1; }
        function next() { nextCount += 1; }
        function raise() { raiseCount += 1; }
    }
    FakePlayer { id: browser; dbusName: "org.mpris.MediaPlayer2.chromium.instance1"; desktopEntry: "chromium"; isPlaying: true }
    FakePlayer { id: paused; dbusName: "org.mpris.MediaPlayer2.spotify.a"; desktopEntry: "spotify.desktop" }
    FakePlayer { id: playing; dbusName: "org.mpris.MediaPlayer2.spotify.z"; desktopEntry: "spotify"; isPlaying: true }
    FakePlayer { id: flatpak; dbusName: "org.mpris.MediaPlayer2.synthetic"; desktopEntry: "com.spotify.Client.desktop" }
    Component.onCompleted: {
        S.Media.player = browser;
        S.Media.players = [browser];
        check(!S.WidgetMedia.available, "browser identity was mistaken for Spotify");
        S.Media.players = [paused, browser, playing];
        check(S.WidgetMedia.player === playing, "playing Spotify was not preferred");
        check(S.Media.player === browser, "widget changed the shared media selection");
        check(S.WidgetMedia.title === playing.trackTitle && S.WidgetMedia.artUrl === playing.trackArtUrl, "Spotify metadata was not selected");
        check(!S.WidgetMedia.progressActive, "hidden widget started progress updates");
        S.WidgetMedia.displayActive = true;
        check(S.WidgetMedia.progressActive && S.WidgetMedia.progressInterval === 1000, "AC progress policy is wrong");
        S.Battery.onBattery = true;
        S.Battery.profile = "performance";
        check(S.WidgetMedia.progressInterval === 5000, "physical battery was bypassed by profile");
        S.Battery.onBattery = false;
        S.Battery.profile = "power-saver";
        check(S.WidgetMedia.progressInterval === 5000, "power saver did not slow progress sampling");
        S.Battery.profile = "balanced";
        check(S.WidgetMedia.progressInterval === 1000, "AC sampling did not recover");
        playing.position = 47;
        check(S.WidgetMedia.position === 47, "native position update was lost");
        playing.positionSupported = false;
        check(!S.WidgetMedia.progressActive, "unsupported position started a timer");
        playing.positionSupported = true;
        playing.lengthSupported = false;
        check(!S.WidgetMedia.progressActive, "unsupported length started a timer");
        playing.lengthSupported = true;
        S.WidgetMedia.previous(); S.WidgetMedia.toggle(); S.WidgetMedia.next(); S.WidgetMedia.openSpotify();
        check(playing.previousCount === 1 && playing.toggleCount === 1 && playing.nextCount === 1 && playing.raiseCount === 1,
              "Spotify controls did not target the independent player");
        S.Desktop.preview = true;
        S.WidgetMedia.previous(); S.WidgetMedia.toggle(); S.WidgetMedia.next(); S.WidgetMedia.openSpotify();
        check(playing.previousCount === 1 && playing.toggleCount === 1 && playing.nextCount === 1 && playing.raiseCount === 1,
              "preview invoked media controls");
        S.Desktop.preview = false;
        playing.isPlaying = false;
        check(S.WidgetMedia.player === paused && !S.WidgetMedia.progressActive, "paused Spotify preference or progress policy is wrong");
        S.Media.players = [flatpak];
        check(S.WidgetMedia.player === flatpak, "Flatpak Spotify identity was not supported");
        S.Media.players = [];
        check(!S.WidgetMedia.available && S.WidgetMedia.position === 0 && !S.WidgetMedia.progressActive,
              "removed player left active progress state");
        console.info("SUMI_WIDGET_SERVICES_OK", "media");
        finished.start();
    }
    Timer { id: finished; interval: 1; onTriggered: Qt.quit() }
}
'''


def atomic_replace(path: Path, content: str) -> None:
    staged = path.with_name(path.name + ".next")
    staged.write_text(content)
    staged.chmod(0o600)
    staged.replace(path)


def document(text="") -> dict:
    return {"version": 1, "enabled": {"clock": True, "spotify": True, "priorities": True, "deadline": True},
            "priorities": [{"text": text, "done": False}, {"text": "", "done": False}, {"text": "", "done": False}],
            "deadline": {"title": "", "at": None}, "layouts": {"synthetic-image": "right"}}


def fixture(repo: Path, work: Path, mode: str) -> tuple[Path, dict]:
    shell = work / "shell"
    services = shell / "services"
    config = shell / "config"
    services.mkdir(parents=True)
    config.mkdir()
    for name in ("Widgets", "WidgetMedia"):
        shutil.copy2(repo / "shell/services" / (name + ".qml"), services / (name + ".qml"))
    (services / "Desktop.qml").write_text(DESKTOP)
    (services / "Clock.qml").write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nSingleton { property date date: new Date(1800000000000) }\n')
    (services / "Media.qml").write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nSingleton { property var players: []; property var player: null }\n')
    (services / "Battery.qml").write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nSingleton { property bool onBattery: false; property string profile: "balanced" }\n')
    (services / "qmldir").write_text("".join(f"singleton {name} {name}.qml\n" for name in ("Widgets", "WidgetMedia", "Desktop", "Clock", "Media", "Battery")))
    (config / "Theme.qml").write_text(THEME)
    (config / "qmldir").write_text("singleton Theme Theme.qml\n")
    (shell / "shell.qml").write_text(MEDIA_HARNESS if mode == "media" else STORAGE_HARNESS)
    runtime = work / "runtime"
    runtime.mkdir(mode=0o700)
    state = work / "state"
    state.mkdir(mode=0o700)
    (state / "gate.json").write_text('{"ready":false}')
    if mode == "retry":
        (state / "widgets.json").mkdir()
    environment = dict(os.environ, SUMI_PREVIEW="1" if mode == "preview" else "0", SUMI_TEST_MODE=mode,
                       SUMI_HOME=str(work / "home"), SUMI_STATE_DIR=str(state), SUMI_DATA_DIR=str(work / "data"),
                       SUMI_DESKTOPCTL=str(repo / "bin/desktopctl"), QT_QPA_PLATFORM="offscreen",
                       XDG_RUNTIME_DIR=str(runtime), DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent")
    return shell, environment


def run_mode(repo: Path, mode: str) -> None:
    with tempfile.TemporaryDirectory(prefix=f"sumi-widget-services-{mode}-") as temporary:
        work = Path(temporary)
        shell, environment = fixture(repo, work, mode)
        state = work / "state"
        process = subprocess.Popen(["qs", "-p", str(shell)], env=environment, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        lines = []
        watchdog = threading.Timer(12, process.kill)
        watchdog.start()
        try:
            for line in process.stdout:
                lines.append(line)
                if "SUMI_WIDGET_COALESCED" in line:
                    saved = json.loads((state / "widgets.json").read_text())
                    if saved["priorities"][0]["text"] != "Final edit":
                        raise AssertionError("Native save did not persist the final coalesced edit")
                    if stat.S_IMODE(state.stat().st_mode) != 0o700 or stat.S_IMODE((state / "widgets.json").stat().st_mode) != 0o600:
                        raise AssertionError("Native widget storage was not private")
                    atomic_replace(state / "widgets.json", "{invalid-json")
                elif "SUMI_WIDGET_WRITE_SCHEMA_INVALID" in line:
                    invalid = document("Invalid schema edit")
                    invalid["extra"] = "unexpected"
                    atomic_replace(state / "widgets.json", json.dumps(invalid))
                    atomic_replace(state / "gate.json", '{"ready":true}')
                elif "SUMI_WIDGET_WRITE_VALID" in line:
                    atomic_replace(state / "widgets.json", json.dumps(document("External edit")))
                elif "SUMI_WIDGET_RETRY_READY" in line:
                    (state / "widgets.json").rmdir()
                    atomic_replace(state / "gate.json", '{"ready":true}')
            process.wait(timeout=5)
        finally:
            watchdog.cancel()
            if process.poll() is None:
                process.kill()
                process.wait()
        output = "".join(lines)
        if (process.returncode or f"SUMI_WIDGET_SERVICES_OK {mode}" not in output
                or any(token in output for token in ("SUMI_WIDGET_SERVICES_FAILED", "TypeError:", "ReferenceError:"))):
            raise SystemExit(output)
        if mode == "preview" and sorted(item.name for item in state.iterdir()) != ["gate.json"]:
            raise SystemExit("Preview wrote personal widget state\n" + output)
        if mode == "retry" and json.loads((state / "widgets.json").read_text())["priorities"][0]["text"] != "Retry content":
            raise SystemExit("Retry did not persist the retained edit\n" + output)
        labels = {
            "persist": "native stdin saves coalesce; private disk state; atomic invalid replacements retain last valid data",
            "retry": "failed native save preserves edits and explicit retry recovers",
            "preview": "preview rejects personal edits and creates no widget files",
            "media": "independent Spotify selection; browser exclusion; playback controls; battery and visibility progress policy",
        }
        print("PASS: " + labels[mode])


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    for mode in ("persist", "retry", "preview", "media"):
        run_mode(repo, mode)


if __name__ == "__main__":
    main()
