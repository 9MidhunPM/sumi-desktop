import QtQuick
import QtMultimedia
import Quickshell

// Audio devices are initialized only when the companion supplies local speech.
Scope {
    id: root
    property url source: ""
    property bool muted: false
    readonly property int position: player.position
    readonly property bool playing: !muted && player.hasAudio && player.playbackState === MediaPlayer.PlayingState && player.error === MediaPlayer.NoError
    signal finished(bool failed)
    AudioOutput { id: output; muted: root.muted; volume: 1 }
    MediaPlayer {
        id: player
        audioOutput: output
        source: root.source
        onSourceChanged: { if (source.toString()) Qt.callLater(play); else stop(); }
        onMediaStatusChanged: if (mediaStatus === MediaPlayer.EndOfMedia) root.finished(false)
        onErrorOccurred: (error, errorString) => root.finished(true)
    }
}
