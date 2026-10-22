pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import "../config" as C

Singleton {
    id: root
    readonly property string stateDir: C.Theme.stateDir
    property var document: defaults()
    property var committedScene: null
    property bool sceneFromDisk: false
    property var catalog: []
    property bool loaded: false
    property bool savePending: false
    property string error: ""
    signal saved(bool ok)
    readonly property bool saving: saver.running || savePending
    readonly property var scene: committedScene || fallbackScene()
    readonly property string layoutMode: document.layouts[scene.imageKey] || "curated"
    readonly property string deadlineText: deadlineLabel(Clock.date.getTime())

    function defaults() {
        return {version: 1, enabled: {clock: true, spotify: true, priorities: true, deadline: true},
            priorities: [{text: "", done: false}, {text: "", done: false}, {text: "", done: false}],
            deadline: {title: "", at: null}, layouts: {}};
    }
    function keysMatch(value, keys) {
        return value && typeof value === "object" && !Array.isArray(value)
            && Object.keys(value).length === keys.length && keys.every(key => Object.prototype.hasOwnProperty.call(value, key));
    }
    function valid(value) {
        return keysMatch(value, ["version", "enabled", "priorities", "deadline", "layouts"]) && value.version === 1
            && keysMatch(value.enabled, ["clock", "spotify", "priorities", "deadline"])
            && ["clock", "spotify", "priorities", "deadline"].every(key => typeof value.enabled[key] === "boolean")
            && Array.isArray(value.priorities) && value.priorities.length === 3
            && value.priorities.every(item => keysMatch(item, ["text", "done"]) && typeof item.text === "string" && item.text.length <= 180 && item.text.indexOf("\0") < 0 && typeof item.done === "boolean")
            && keysMatch(value.deadline, ["title", "at"]) && typeof value.deadline.title === "string" && value.deadline.title.length <= 160 && value.deadline.title.indexOf("\0") < 0
            && (value.deadline.at === null || (typeof value.deadline.at === "number" && Number.isInteger(value.deadline.at)
                && value.deadline.at >= 0 && value.deadline.at <= 8640000000000000))
            && value.layouts && typeof value.layouts === "object" && !Array.isArray(value.layouts)
            && Object.keys(value.layouts).length <= 256
            && Object.keys(value.layouts).every(key => key.length > 0 && key.length <= 512 && key.indexOf("\0") < 0 && ["left", "right", "split"].indexOf(value.layouts[key]) >= 0);
    }
    function validScene(value) {
        return value && value.version === 1 && typeof value.imageKey === "string" && typeof value.wallpaper === "string"
            && Array.isArray(value.sourceSize) && value.sourceSize.length === 2 && value.sourceSize.every(n => Number.isInteger(n) && n > 0 && n <= 100000)
            && value.layout && ["left", "right", "split"].indexOf(value.layout.mode) >= 0 && value.layout.anchors
            && ["clock", "spotify", "priorities", "deadline"].every(key => Array.isArray(value.layout.anchors[key])
                && value.layout.anchors[key].length === 2 && value.layout.anchors[key].every(n => Number.isFinite(n) && n >= 0 && n <= 1));
    }
    function fallbackScene() {
        const theme = C.Theme.document;
        const candidate = catalog.find(item => item.wallpaper === C.Theme.wallpaper) || theme;
        return {version: 1, imageKey: candidate.imageKey || C.Theme.wallpaper || "default", wallpaper: C.Theme.wallpaper,
            sourceSize: candidate.sourceSize || [1920, 1080],
            layout: candidate.desktopLayout || {mode: "left", compact: true,
                anchors: {clock: [0.05, 0.18], spotify: [0.05, 0.38], priorities: [0.05, 0.58], deadline: [0.05, 0.79]}}};
    }
    function loadDocument() {
        // A queued edit is newer than a watcher event from our previous save.
        if (saver.running || savePending) return;
        try {
            const value = JSON.parse(widgetFile.text());
            if (!valid(value)) throw new Error("Invalid widget data");
            document = value;
            error = "";
        } catch (failure) { error = "Widget data could not be read. Your current values have been kept."; }
        loaded = true;
    }
    function saveDocument(value) {
        if (Desktop.preview) { error = "Preview · personal changes are disabled"; return false; }
        if (!loaded) { error = "Your widgets are still loading. Try again in a moment."; return false; }
        if (!valid(value)) { error = "Check the priorities and deadline before saving."; return false; }
        document = JSON.parse(JSON.stringify(value));
        persist();
        return true;
    }
    function persist() {
        if (saver.running) { savePending = true; return; }
        savePending = false;
        saver.payload = JSON.stringify(document);
        saver.stdinEnabled = true;
        saver.running = true;
    }
    function retrySave() { if (!Desktop.preview && loaded) persist(); }
    function togglePriority(index) {
        if (index < 0 || index >= 3 || !document.priorities[index].text.trim()) return;
        const value = JSON.parse(JSON.stringify(document));
        value.priorities[index].done = !value.priorities[index].done;
        saveDocument(value);
    }
    function setLayout(mode) {
        if (["curated", "left", "right", "split"].indexOf(mode) < 0) return;
        const value = JSON.parse(JSON.stringify(document));
        if (mode === "curated") delete value.layouts[scene.imageKey];
        else value.layouts[scene.imageKey] = mode;
        saveDocument(value);
    }
    function deadlineLabel(now) {
        const at = document.deadline.at;
        if (at === null) return "Set a deadline";
        const difference = at - now;
        if (difference === 0) return "Due now";
        const minutes = Math.max(1, Math.ceil(Math.abs(difference) / 60000));
        const days = Math.floor(minutes / 1440);
        const hours = Math.floor(minutes / 60) % 24;
        const remaining = minutes % 60;
        const duration = days ? days + "d " + hours + "h" : hours ? hours + "h " + remaining + "m" : minutes + "m";
        return difference < 0 ? "Overdue by " + duration : duration + " left";
    }
    FileView {
        id: widgetFile
        path: root.stateDir + "/widgets.json"
        preload: true
        printErrors: false
        watchChanges: true
        onLoaded: root.loadDocument()
        onLoadFailed: failure => {
            root.loaded = true;
            if (failure !== FileViewError.FileNotFound) root.error = "Widget data could not be read. Your current values have been kept.";
        }
        onFileChanged: reload()
    }
    FileView {
        id: sceneFile
        path: root.stateDir + "/scene.json"
        preload: true
        printErrors: false
        watchChanges: true
        onLoaded: {
            try {
                const value = JSON.parse(text());
                if (!root.validScene(value)) throw new Error("Invalid scene");
                root.committedScene = value;
                root.sceneFromDisk = true;
            } catch (failure) { console.warn("Sumi: keeping last valid widget scene"); }
        }
        onLoadFailed: failure => {
            if (failure === FileViewError.FileNotFound && root.sceneFromDisk) {
                root.sceneFromDisk = false;
                root.committedScene = root.fallbackScene();
            }
        }
        onFileChanged: reload()
    }
    // One startup lookup upgrades an existing install whose theme predates
    // scene metadata. It never applies a theme or changes the wallpaper.
    Process {
        command: [Desktop.controller, "theme", "list", "--json"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.catalog = JSON.parse(text); } catch (failure) {}
                // Latch a pre-scene install once. Later palette writes must not
                // reposition widgets before awww has accepted the new image.
                if (!root.committedScene) root.committedScene = root.fallbackScene();
            }
        }
        stderr: StdioCollector {}
    }
    Process {
        id: saver
        property string payload: ""
        command: [Desktop.controller, "widgets", "save"]
        stdout: StdioCollector {}
        stderr: StdioCollector {}
        onStarted: { write(payload); stdinEnabled = false; }
        onExited: (code, status) => {
            root.error = code === 0 ? "" : "Your widgets could not be saved. Check the state directory and retry.";
            if (root.savePending) Qt.callLater(root.persist);
            else root.saved(code === 0);
        }
    }
}
