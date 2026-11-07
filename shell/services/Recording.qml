pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

// The controller validates ownership against /proc before stopping anything.
// Receipt changes discover CLI recordings; only an active recording is polled.
Singleton {
    id: root
    property bool ready: false
    property bool recording: false
    property bool busy: false
    property string file: ""
    property string error: ""
    property bool refreshPending: false
    signal completed(string operation, var result)
    readonly property string runtimeDir: Quickshell.env("XDG_RUNTIME_DIR")
    readonly property bool observeReceipt: !Desktop.preview && Quickshell.env("SUMI_PREVIEW") !== "1" && runtimeDir.length > 0
    readonly property string receiptPath: runtimeDir + "/sumi/recorder.json"

    function apply(result): bool {
        if (typeof result.recording !== "boolean") return false;
        recording = result.recording;
        file = result.file || "";
        ready = true;
        return true;
    }
    function refresh(preserveError = false): void {
        if (Desktop.preview) return;
        if (busy) { refreshPending = true; return; }
        busy = true;
        refreshPending = false;
        Desktop.action("record", ["status"], function(ok, result, detail) {
            root.busy = false;
            root.ready = ok && root.apply(result);
            if (!root.ready) root.error = detail || "Recording status is unavailable.";
            else if (!preserveError) root.error = "";
            if (root.refreshPending) refreshDelay.restart();
        });
    }
    function operate(operation, callback = null): void {
        if (Desktop.preview || busy || (operation === "stop" && !recording)) {
            if (typeof callback === "function") callback(false, {}, Desktop.preview ? "Preview · desktop changes are disabled" : "Recording control is busy or unavailable.");
            return;
        }
        busy = true;
        error = "";
        Desktop.action("record", [operation], function(ok, result, detail) {
            root.busy = false;
            const valid = ok && root.apply(result);
            if (valid) { if (root.refreshPending) refreshDelay.restart(); }
            else { root.error = detail || "Could not " + operation + " recording."; root.refresh(true); }
            if (valid && !result.cancelled && ((operation === "start" && result.recording)
                    || (operation === "stop" && !result.recording && result.stopped === true)))
                root.completed(operation, result);
            if (typeof callback === "function") callback(valid, result, valid ? "" : root.error);
        });
    }
    // Call start only after dismissing the island/panel for the region selector.
    function start(callback = null): void { operate("start", callback); }
    function stop(): void { operate("stop"); }
    Timer { id: activeCheck; interval: 5000; repeat: true; running: root.recording && !Desktop.preview; onTriggered: root.refresh() }
    Timer { id: refreshDelay; interval: 80; onTriggered: root.refresh() }
    FileView {
        id: receipt
        path: root.observeReceipt ? root.receiptPath : ""
        watchChanges: root.observeReceipt
        preload: root.observeReceipt
        printErrors: false
        onFileChanged: { reload(); refreshDelay.restart(); }
    }
    Component.onCompleted: if (observeReceipt) refresh()
}
