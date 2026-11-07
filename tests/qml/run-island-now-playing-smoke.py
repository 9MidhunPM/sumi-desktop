#!/usr/bin/env python3
"""Check the now-playing layout and power selector using isolated UI fixtures."""
import contextlib
import importlib.util
import io
from pathlib import Path


def main():
    path = Path(__file__).with_name('run-island-dashboard-smoke.py')
    spec = importlib.util.spec_from_file_location('dashboard_fixture', path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    fixture.STUBS['IslandMedia'] = fixture.STUBS['IslandMedia'].replace(
        'function toggle() {}', 'property int toggleCalls: 0\nfunction toggle() { toggleCalls++; playing = !playing; }').replace(
        'function seek(value) {}', 'property real lastSeek: 0\nfunction seek(value) { lastSeek = value; }')
    start = fixture.HARNESS.index('            function test_dashboard() {')
    fixture.HARNESS = fixture.HARNESS[:start] + '''            function test_dashboard() {
                const player = {identity: "Fixture Player", dbusName: "org.mpris.MediaPlayer2.fixture", trackTitle: "A deliberately long real-song fixture title that must wrap inside the compact island", trackArtist: "Fixture artist", canTogglePlaying: true, canGoPrevious: true, canGoNext: true, canSeek: true, lengthSupported: true, positionSupported: true, length: 245, position: 75};
                S.Media.players = [player]; S.IslandMedia.player = player;
                S.IslandMedia.available = true; S.IslandMedia.playing = true;
                S.IslandMedia.title = player.trackTitle; S.IslandMedia.artist = player.trackArtist;
                S.IslandMedia.artUrl = Qt.resolvedUrl("assets/icons/music.svg");
                dashboard.mediaPosition = 75; dashboard.section = "media";
                wait(350);
                check(findChild(dashboard, "islandNowPlayingArtwork").visible, "Real artwork fixture is displayed");
                check(findChild(dashboard, "islandNowPlayingArtwork").width >= 160, "Now playing has a substantial cover");
                check(findChild(dashboard, "islandNowPlayingPosition").text === "1:15", "Elapsed MPRIS time is shown");
                check(findChild(dashboard, "islandNowPlayingDuration").text === "4:05", "MPRIS duration is shown");
                findChild(dashboard, "islandDashboardPlay").clicked();
                check(S.IslandMedia.toggleCalls === 1 && !S.IslandMedia.playing, "Primary transport toggles the chosen source");
                const seek = findChild(dashboard, "islandNowPlayingSeek");
                check(seek.enabled && seek.to === 245, "Seeking uses the actual track length");
                seek.value = 120; seek.moved();
                check(S.IslandMedia.lastSeek === 120, "Seek movement reaches the media service");
                const page = findChild(dashboard, "islandMediaPage");
                check(!page.sourcesExpanded, "Source chooser starts collapsed");
                findChild(dashboard, "islandNowPlayingSources").clicked();
                check(page.sourcesExpanded, "Source chooser opens on demand");
                dashboard.anchors.fill = null; dashboard.width = 280; dashboard.height = 488;
                wait(100);
                const title = findChild(dashboard, "islandDashboardTrackTitle");
                check(title.lineCount <= 2 && title.mapToItem(dashboard,0,0).x + title.width <= 281, "Long title stays within narrow layout");
                dashboard.section = "controls"; wait(350);
                const saver = findChild(dashboard, "islandPowerProfile-power-saver");
                const performance = findChild(dashboard, "islandPowerProfile-performance");
                saver.clicked();
                check(S.Battery.profile === "power-saver" && saver.selected, "Power saver selection is backed by the service");
                S.Battery.performanceAvailable = false;
                check(!performance.enabled, "Unavailable performance mode is disabled");
                findChild(dashboard, "islandPowerProfile-balanced").clicked();
                check(S.Battery.profile === "balanced", "Balanced remains available");
                console.info("ISLAND_DASHBOARD_OK"); Qt.quit();
            }
        }
    }
}
'''
    with contextlib.redirect_stdout(io.StringIO()):
        fixture.main()
    print('PASS: large real cover; elapsed/duration; transport/seek; collapsed source chooser; narrow long title; actual power profiles and availability')


if __name__ == '__main__':
    main()
