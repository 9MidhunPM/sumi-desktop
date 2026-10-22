pragma Singleton

import QtQuick
import Quickshell

Singleton {
    id: root
    property bool displayActive: false
    readonly property var player: choosePlayer(Media.players)
    readonly property bool available: player !== null
    readonly property bool playing: !!player && player.isPlaying
    readonly property string title: player ? (player.trackTitle || "Spotify") : "Your next soundtrack"
    readonly property string artist: player ? (player.trackArtist || "Spotify") : "Open Spotify to play something"
    readonly property string artUrl: player ? player.trackArtUrl || "" : ""
    readonly property real length: player && player.lengthSupported ? Math.max(0, player.length) : 0
    property real position: 0
    readonly property bool progressActive: displayActive && playing && !!player && player.positionSupported && length > 0
    readonly property int progressInterval: Battery.onBattery || Battery.profile === "power-saver" ? 5000 : 1000
    property string error: ""

    function choosePlayer(players) {
        const matches = players.filter(item => /^org\.mpris\.MediaPlayer2\.spotify(?:\.|$)/i.test(item.dbusName || "")
            || ["spotify", "com.spotify.Client"].indexOf((item.desktopEntry || "").replace(/\.desktop$/, "")) >= 0);
        matches.sort((a, b) => String(a.dbusName).localeCompare(String(b.dbusName)));
        return matches.find(item => item.isPlaying) || matches[0] || null;
    }
    function refreshPosition() { position = player && player.positionSupported ? Math.max(0, player.position) : 0; }
    onPlayerChanged: refreshPosition()
    onProgressActiveChanged: refreshPosition()
    onLengthChanged: refreshPosition()
    Connections {
        target: root.player
        function onPositionChanged() { root.refreshPosition(); }
        function onTrackChanged() { root.refreshPosition(); }
    }
    Timer { interval: root.progressInterval; repeat: true; running: root.progressActive; onTriggered: root.refreshPosition() }
    function previous() { if (player && player.canGoPrevious && !Desktop.preview) player.previous(); }
    function toggle() { if (player && player.canTogglePlaying && !Desktop.preview) player.togglePlaying(); }
    function next() { if (player && player.canGoNext && !Desktop.preview) player.next(); }
    function openSpotify() {
        if (Desktop.preview) return;
        if (player && player.canRaise) { player.raise(); return; }
        const entry = DesktopEntries.applications.values.find(item => ["spotify", "com.spotify.Client"].indexOf(item.id.replace(/\.desktop$/, "")) >= 0);
        if (!entry) { error = "Spotify is not installed."; return; }
        error = "";
        Desktop.action("launch-desktop", [entry.id], null);
    }
}
