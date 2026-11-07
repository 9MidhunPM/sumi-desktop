#!/usr/bin/env python3
"""Check activity-aware island selection without changing global MPRIS choice."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "services" as S
ShellRoot {
    QtObject {
        id: browser
        property string identity: "Brave"
        property string desktopEntry: "brave-browser"
        property string dbusName: "org.mpris.MediaPlayer2.chromium.instance1"
        property string trackTitle: "Brave"
        property string trackArtist: ""
        property string trackArtUrl: ""
        property bool isPlaying: false
        property bool canTogglePlaying: true
        property bool canGoNext: true
        property bool canGoPrevious: true
        property bool canRaise: true
        property bool canSeek: true
        property real position: 0
        property int toggles: 0
        function togglePlaying() { toggles++; }
        function next() {} function previous() {} function raise() {}
    }
    QtObject {
        id: spotify
        property string identity: "Spotify"
        property string desktopEntry: "com.spotify.Client"
        property string dbusName: "org.mpris.MediaPlayer2.spotify.instance2"
        property string trackTitle: "A real song"
        property string trackArtist: "An artist"
        property string trackArtUrl: "file:///synthetic/art.png"
        property bool isPlaying: true
        property bool canTogglePlaying: true
        property bool canGoNext: true
        property bool canGoPrevious: true
        property bool canRaise: true
        property bool canSeek: true
        property real position: 0
        property int toggles: 0
        property int nexts: 0
        property int previouses: 0
        property int raises: 0
        function togglePlaying() { toggles++; }
        function next() { nexts++; }
        function previous() { previouses++; }
        function raise() { raises++; }
    }
    TestCase {
        name: "IslandMedia"
        when: true
        function check(value, message) {
            if (!value) { console.error("ISLAND_MEDIA_FAILED", message); Qt.exit(1); throw new Error(message); }
        }
        function test_activity() {
            S.Media.selectedBus = browser.dbusName;
            S.Media.players = [browser]; wait(1);
            check(!S.IslandMedia.available && !S.IslandMedia.playing && S.IslandMedia.title === "Nothing playing", "Idle browser registration is not playback");
            browser.trackTitle = "A stale video title"; wait(1);
            check(!S.IslandMedia.available, "Paused browser metadata is ignored even when stale title remains");
            browser.isPlaying = true; browser.trackTitle = "Brave Browser"; wait(1);
            check(!S.IslandMedia.available, "Generic browser title is not meaningful playback");
            browser.trackTitle = "A real playing video"; wait(1);
            check(S.IslandMedia.player === browser && S.IslandMedia.playing, "Actual browser playback remains available");
            S.Media.players = [browser, spotify]; wait(1);
            check(S.IslandMedia.player === spotify && S.Media.selectedBus === browser.dbusName, "Playing Spotify wins without changing the global selection");
            S.IslandMedia.select(browser); wait(1);
            check(S.IslandMedia.player === browser, "Explicit meaningful player selection overrides automatic Spotify priority");
            browser.isPlaying = false; wait(1);
            check(S.IslandMedia.player === spotify, "A paused browser cannot hide playing Spotify");
            S.IslandMedia.select(null);
            spotify.isPlaying = false; wait(1);
            check(S.IslandMedia.player === spotify && S.IslandMedia.available && !S.IslandMedia.playing, "Paused native song remains available for resume");
            S.IslandMedia.toggle(); S.IslandMedia.next(); S.IslandMedia.previous(); S.IslandMedia.raise(); S.IslandMedia.seek(14);
            check(spotify.toggles === 1 && spotify.nexts === 1 && spotify.previouses === 1 && spotify.raises === 1 && spotify.position === 14 && browser.toggles === 0, "All controls target the selected island player");
            check(S.IslandMedia.title === spotify.trackTitle && S.IslandMedia.artist === spotify.trackArtist && S.IslandMedia.artUrl === spotify.trackArtUrl, "Metadata follows the actual selected player");
            spotify.trackTitle = "Spotify"; wait(1);
            check(!S.IslandMedia.available, "Identity-only native metadata also has no media card");
            spotify.trackTitle = ""; spotify.isPlaying = true; wait(1);
            check(!S.IslandMedia.available, "An empty title never creates a false playing state");
            browser.trackTitle = "Another real video"; browser.isPlaying = true; wait(1);
            check(S.IslandMedia.player === browser, "A meaningful playing browser beats an empty native player");
            S.IslandMedia.select(spotify); wait(1);
            check(S.Media.selectedBus === browser.dbusName && S.IslandMedia.player === browser, "Manual island selection is independent and cannot select empty metadata");
            check(S.IslandMedia.isBrowser({identity:"Zen Browser",desktopEntry:"zen",dbusName:"org.mpris.MediaPlayer2.firefox"}), "Zen is recognized as a browser");
            spotify.trackTitle = "A real song again"; spotify.isPlaying = false;
            S.IslandMedia.select(spotify); wait(1);
            check(S.IslandMedia.player === spotify && !S.IslandMedia.playing, "Explicit paused native selection remains resumable alongside playing browser");
            S.Media.players = [browser]; wait(1);
            check(S.IslandMedia.player === browser, "Removing explicit player falls back to meaningful activity");
            S.Media.players = []; wait(1);
            check(!S.IslandMedia.available, "Removing all players resets the island");
            console.info("ISLAND_MEDIA_OK"); Qt.quit();
        }
    }
}
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sumi-island-media-') as temporary:
        work = Path(temporary)
        services = work / 'services'
        services.mkdir()
        shutil.copy2(repo / 'shell/services/IslandMedia.qml', services)
        (services / 'qmldir').write_text('singleton IslandMedia IslandMedia.qml\nsingleton Media Media.qml\nsingleton Desktop Desktop.qml\n')
        prefix = 'pragma Singleton\nimport QtQuick\nimport Quickshell\nSingleton {\n'
        (services / 'Media.qml').write_text(prefix + 'property var players: []\nproperty string selectedBus: ""\n}')
        (services / 'Desktop.qml').write_text(prefix + 'property bool preview: false\n}')
        (work / 'shell.qml').write_text(HARNESS)
        runtime = work / 'runtime'
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(runtime), SUMI_PREVIEW='1')
        result = subprocess.run(['qs', '-p', str(work)], env=environment, text=True, capture_output=True, timeout=10)
        output = result.stdout + result.stderr
        if result.returncode or 'ISLAND_MEDIA_OK' not in output or any(message in output for message in ['TypeError:', 'ReferenceError:', 'Unable to assign [undefined]', 'Failed to load configuration', 'FAIL!']):
            raise SystemExit(output)
        print('PASS: idle/stale browser exclusion; meaningful browser playback; Spotify preference and paused resume; independent selection; correctly routed controls')


if __name__ == '__main__':
    main()
