import QtQuick
import Quickshell
import Quickshell.Io

// Qt's network loader can stall on Spotify's CDN, and optional image codecs
// are not present on every Qt installation. Remote covers become cached PNGs.
Image {
    id: root
    property url artworkUrl: ""
    property bool active: true
    readonly property bool remote: /^https?:\/\//i.test(String(artworkUrl))
    property string cachedSource: ""
    property string fetchedFor: ""
    property bool attempted: false
    property bool stopping: false
    readonly property bool loading: fetcher.running || status === Image.Loading
    source: remote ? cachedSource : artworkUrl
    asynchronous: true
    cache: true

    function request() {
        if (!active || !remote || cachedSource || fetcher.running || stopping || attempted) return;
        fetchedFor = String(artworkUrl);
        attempted = true;
        fetcher.command = ["python3", decodeURIComponent(String(Qt.resolvedUrl("../services/fetch-artwork.py")).replace(/^file:\/\//, "")), fetchedFor];
        fetcher.running = true;
    }
    onArtworkUrlChanged: {
        if (fetcher.running) stopping = true;
        fetcher.running = false;
        cachedSource = "";
        attempted = false;
        Qt.callLater(request);
    }
    onActiveChanged: {
        if (!active) {
            if (fetcher.running) stopping = true;
            fetcher.running = false;
            if (!cachedSource) attempted = false;
        } else Qt.callLater(request);
    }
    Component.onCompleted: Qt.callLater(request)
    Process {
        id: fetcher
        stdout: StdioCollector { id: result }
        stderr: StdioCollector {}
        onExited: (code, status) => {
            root.stopping = false;
            if (root.fetchedFor === String(root.artworkUrl)) {
                if (code === 0 && root.active && result.text.trim().startsWith("file://")) root.cachedSource = result.text.trim();
            }
            Qt.callLater(root.request);
        }
    }
}
