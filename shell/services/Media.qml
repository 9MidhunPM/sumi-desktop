pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Services.Mpris as Mp

Singleton {
    id: root
    readonly property var players: Mp.Mpris.players.values
    property string selectedBus: ""
    readonly property var player: {
        const chosen = players.find(item => item.dbusName === selectedBus);
        return chosen || players.find(item => item.isPlaying) || players[0] || null;
    }
    readonly property bool available: player !== null
    readonly property bool playing: player ? player.isPlaying : false
    readonly property string title: player ? (player.trackTitle || player.identity) : "A quiet moment"
    readonly property string artist: player ? (player.trackArtist || player.identity) : "Nothing playing"
    readonly property string artUrl: player ? player.trackArtUrl : ""

    function select(value: var): void { selectedBus = value ? value.dbusName : ""; }
    function toggle(): void { if (player && player.canTogglePlaying && !Desktop.preview) player.togglePlaying(); }
    function next(): void { if (player && player.canGoNext && !Desktop.preview) player.next(); }
    function previous(): void { if (player && player.canGoPrevious && !Desktop.preview) player.previous(); }
    function raise(): void { if (player && player.canRaise && !Desktop.preview) player.raise(); }
    function seek(value: real): void { if (player && player.canSeek && !Desktop.preview) player.position = value; }
}
