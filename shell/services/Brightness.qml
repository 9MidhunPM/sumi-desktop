pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

// One serialized controller for every brightness control. The observer reads
// kernel change notifications, including changes made by existing hardware keys.
Singleton {
    id: root
    property real percent: 0
    property bool ready: false
    readonly property bool available: ready
    property bool loading: false
    property bool writing: false
    property bool writePending: false
    property bool refreshPending: false
    readonly property bool busy: loading || writing || writePending
    property string error: ""
    property int serial: 0
    property int retryCount: 0
    property bool observed: false
    property real observedPercent: 0
    property double watchStartedAt: 0
    readonly property bool observerEnabled: !Desktop.preview && Quickshell.env("SUMI_PREVIEW") !== "1"
    signal changed(real value)
    onObserverEnabledChanged: {
        retry.stop();
        watcher.running = observerEnabled;
        if (!observerEnabled) observed = false;
        else retryCount = 0;
    }

    function accept(value, notify): bool {
        if (typeof value !== "number" || !isFinite(value) || value < 0 || value > 100) return false;
        const different = notify && observed && Math.abs(value - observedPercent) > 0.0001;
        // Command reads update controls, but must neither arm the observer nor
        // consume a kernel change that has not reached the event stream yet.
        if (notify) { observedPercent = value; observed = true; }
        ready = true;
        if (!writing && !writePending) percent = value;
        if (notify && different) changed(value);
        return true;
    }
    function refresh(): void {
        if (Desktop.preview) return;
        if (observerEnabled && !watcher.running && !retry.running) { retryCount = 0; watcher.running = true; }
        if (loading || writing || writePending) { refreshPending = true; return; }
        refreshPending = false;
        const request = ++serial;
        loading = true;
        Desktop.action("brightness-get", [], function(ok, result, detail) {
            root.loading = false;
            if (request !== root.serial) {
                if (root.refreshPending && !root.writing && !root.writePending) root.refresh();
                return;
            }
            const valid = ok && typeof result.percent === "number" && isFinite(result.percent) && result.percent >= 0 && result.percent <= 100;
            root.ready = valid;
            if (valid) { root.accept(result.percent, false); root.error = ""; }
            else root.error = detail || "Display brightness is unavailable.";
            root.refreshPending = false;
        });
    }
    function setPercent(value): void {
        if (Desktop.preview || !ready || !isFinite(value)) return;
        percent = Math.max(1, Math.min(100, Math.round(value)));
        error = "";
        ++serial;
        writePending = true;
        commitDelay.restart();
    }
    function commit(): void {
        if (writing || !writePending) return;
        writePending = false;
        writing = true;
        const value = percent;
        Desktop.action("brightness", [value], function(ok, result, detail) {
            root.writing = false;
            if (root.writePending) { commitDelay.stop(); root.commit(); }
            else if (!ok) { root.error = detail || "Could not change brightness."; root.refresh(); }
            else root.refresh();
        });
    }
    function observedLine(line): void {
        try {
            const result = JSON.parse(line);
            ++serial; // An older command read cannot overwrite a kernel event.
            if (result.available === false) { ready = false; error = result.error || "Display brightness is unavailable."; return; }
            if (!accept(result.percent, true)) { ready = false; error = "Display brightness returned an invalid value."; return; }
            error = "";
            if (Date.now() - watchStartedAt > 30000) retryCount = 0;
        } catch (parseError) { error = "Display brightness could not be read."; }
    }
    Timer { id: commitDelay; interval: 70; onTriggered: root.commit() }
    Timer { id: retry; onTriggered: if (root.observerEnabled) watcher.running = true }
    Process {
        id: watcher
        command: [typeof Desktop.controller === "string" ? Desktop.controller : "", "action", "brightness-watch"]
        running: root.observerEnabled
        onStarted: root.watchStartedAt = Date.now()
        stdout: SplitParser { onRead: data => root.observedLine(data) }
        stderr: StdioCollector {}
        onExited: (code, status) => {
            if (!root.observerEnabled) return;
            ++root.serial;
            root.observed = false;
            root.ready = false;
            if (!root.error) root.error = "Display brightness observer is unavailable.";
            if (root.retryCount < 5) {
                retry.interval = Math.min(30000, 1000 * Math.pow(2, root.retryCount++));
                retry.restart();
            }
        }
    }
}
