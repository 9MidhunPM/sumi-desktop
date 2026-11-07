pragma Singleton

import QtQuick
import Quickshell

// The island represents meaningful activity, not merely a registered MPRIS
// endpoint. Browser players commonly outlive their audio/video tabs.
Singleton {
    id: root
    property string selectedBus: ""
    readonly property var player: explicitlySelectedPlayer() || choosePlayer(Media.players, Media.selectedBus)
    readonly property bool available: player !== null
    readonly property bool playing: !!player && player.isPlaying
    readonly property string title: player ? String(player.trackTitle || "").trim() : "Nothing playing"
    readonly property string artist: player ? String(player.trackArtist || "").trim() : ""
    readonly property string artUrl: player ? player.trackArtUrl || "" : ""

    function normalized(value) { return String(value || "").trim().toLowerCase().replace(/\s+/g, " "); }
    function isBrowser(item) {
        const identity = [item.identity, item.desktopEntry, item.dbusName].join(" ").toLowerCase();
        return /brave|chromium|chrome|firefox|\bzen\b|webkit|vivaldi|opera|\bedge\b|epiphany/.test(identity);
    }
    function isSpotify(item) {
        return /^org\.mpris\.MediaPlayer2\.spotify(?:\.|$)/i.test(item.dbusName || "")
            || /^(spotify|com\.spotify\.client)(?:\.desktop)?$/i.test(item.desktopEntry || "");
    }
    function meaningful(item) {
        const title = normalized(item.trackTitle);
        if (!title || title === normalized(item.identity)) return false;
        return !/^(spotify|brave(?: browser)?|chromium|google chrome|chrome|firefox|mozilla firefox|zen(?: browser)?|webkit|media player|unknown(?: title)?|nothing playing|no media|a quiet moment)$/.test(title);
    }
    function choosePlayer(players, preferredBus) {
        const candidates = (players || []).filter(item => item && meaningful(item));
        candidates.sort((left, right) => String(left.dbusName || "").localeCompare(String(right.dbusName || "")));
        const playing = candidates.filter(item => item.isPlaying);
        if (playing.length)
            return playing.find(isSpotify) || playing.find(item => item.dbusName === preferredBus) || playing[0];
        const paused = candidates.filter(item => !isBrowser(item));
        return paused.find(isSpotify) || paused.find(item => item.dbusName === preferredBus) || paused[0] || null;
    }
    function explicitlySelectedPlayer() {
        if (!selectedBus) return null;
        return Media.players.find(item => item && item.dbusName === selectedBus && meaningful(item)
            && (item.isPlaying || !isBrowser(item))) || null;
    }
    function select(value) { selectedBus = value ? value.dbusName : ""; }
    function toggle() { if (player && player.canTogglePlaying && !Desktop.preview) player.togglePlaying(); }
    function next() { if (player && player.canGoNext && !Desktop.preview) player.next(); }
    function previous() { if (player && player.canGoPrevious && !Desktop.preview) player.previous(); }
    function raise() { if (player && player.canRaise && !Desktop.preview) player.raise(); }
    function seek(value) { if (player && player.canSeek && !Desktop.preview) player.position = value; }
}
