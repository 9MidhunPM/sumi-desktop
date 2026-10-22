pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import "../config" as C
import "LauncherRanking.js" as Ranking

Singleton {
    id: root
    property var document: ({version: 1, entries: {}})
    property bool loaded: false
    property string error: ""
    property var queue: []
    property bool inFlight: false
    readonly property bool busy: inFlight || queue.length > 0
    signal changing()

    function validStats(value) {
        return value && Number.isSafeInteger(value.count) && value.count >= 1
            && Number.isFinite(value.score) && value.score >= 0 && value.score <= value.count
            && Number.isFinite(value.lastUsed) && value.lastUsed >= 0 && value.lastUsed <= Number.MAX_SAFE_INTEGER;
    }
    function accept(value) {
        if (!value || value.version !== 1 || !value.entries || typeof value.entries !== "object" || Array.isArray(value.entries)
            || Object.keys(value.entries).length > 512 || !Object.keys(value.entries).every(function(id) {
                const entry = value.entries[id];
                return /^(app|action):.+/.test(id) && id.length <= 512 && id.indexOf("/") < 0 && validStats(entry) && entry.queries && typeof entry.queries === "object"
                    && !Array.isArray(entry.queries) && Object.keys(entry.queries).length <= 32
                    && Object.keys(entry.queries).every(query => query.length > 0 && query.length <= 120 && Ranking.normalize(query) === query && validStats(entry.queries[query]));
            }))
            throw new Error("Invalid launcher history");
        changing();
        document = value;
        loaded = true;
        error = "";
    }
    function load() {
        // A response to a queued update is newer than its file-watch event.
        if (root.busy) return;
        try { accept(JSON.parse(historyFile.text())); }
        catch (failure) { root.loaded = true; root.error = "Launcher memory could not be read. Reset learning to start fresh."; }
    }
    function record(id, query) {
        if (Desktop.preview || !id) return;
        queue = queue.concat([{operation: "record", payload: JSON.stringify({id: id, query: Ranking.normalize(query).slice(0, 120)})}]);
        dispatch();
    }
    function reset() {
        if (Desktop.preview) return;
        queue = queue.concat([{operation: "reset", payload: ""}]);
        dispatch();
    }
    function dispatch() {
        if (inFlight || worker.running || !queue.length) return;
        const request = queue[0];
        inFlight = true;
        queue = queue.slice(1);
        worker.command = [Desktop.controller, "launcher-history", request.operation];
        worker.payload = request.payload;
        worker.stdinEnabled = true;
        worker.running = true;
        startupCheck.restart();
    }
    FileView {
        id: historyFile
        path: C.Theme.stateDir + "/launcher-history.json"
        preload: true
        watchChanges: true
        printErrors: false
        onLoaded: root.load()
        onFileChanged: reload()
        onLoadFailed: failure => {
            root.loaded = true;
            if (failure !== FileViewError.FileNotFound) root.error = "Launcher memory could not be read. Reset learning to start fresh.";
        }
    }
    Timer {
        id: startupCheck
        interval: 1500
        onTriggered: {
            if (root.inFlight && !worker.running) {
                root.inFlight = false;
                root.error = "Launcher memory could not be saved. Check the desktop controller and retry.";
                Qt.callLater(root.dispatch);
            }
        }
    }
    Process {
        id: worker
        property string payload: ""
        stdout: StdioCollector { id: output }
        stderr: StdioCollector { id: errors }
        onStarted: { if (payload) write(payload); stdinEnabled = false; }
        onExited: (code, status) => {
            startupCheck.stop();
            if (code === 0) {
                try { root.accept(JSON.parse(output.text)); }
                catch (failure) { root.error = "Launcher memory could not be read. Reset learning to start fresh."; }
            } else root.error = "Launcher memory could not be saved. Check the state directory or reset learning.";
            root.inFlight = false;
            if (root.queue.length) Qt.callLater(root.dispatch);
        }
    }
}
