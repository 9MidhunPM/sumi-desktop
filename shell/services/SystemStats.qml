pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

// Every visible dashboard shares one observer. No work is done without demand.
Singleton {
    id: root
    property var consumers: ({})
    property int nextConsumer: 0
    readonly property bool active: !Desktop.preview && Quickshell.env("SUMI_PREVIEW") !== "1"
        && Object.values(consumers).some(value => value === true)
    property bool cpuAvailable: false
    property bool memoryAvailable: false
    property bool storageAvailable: false
    readonly property bool ready: cpuAvailable && memoryAvailable && storageAvailable
    property real cpuPercent: 0
    property real memoryUsed: 0
    property real memoryTotal: 0
    property real storageUsed: 0
    property real storageTotal: 0
    property real storageFree: 0
    readonly property real memoryPercent: memoryAvailable && memoryTotal > 0 ? Math.min(100, memoryUsed / memoryTotal * 100) : 0
    readonly property real storagePercent: storageAvailable && storageTotal > 0 ? Math.min(100, storageUsed / storageTotal * 100) : 0
    property string error: ""
    property int retryCount: 0
    property bool receivedSample: false
    property bool stopping: false
    readonly property bool observing: watcher.running

    function createConsumer() {
        const id = ++nextConsumer;
        consumers = Object.assign({}, consumers, {[id]: false});
        return id;
    }
    function setDemand(id, value) {
        if (!Object.prototype.hasOwnProperty.call(consumers, id)) return;
        consumers = Object.assign({}, consumers, {[id]: value === true});
    }
    function releaseConsumer(id) {
        const next = Object.assign({}, consumers);
        delete next[id]; consumers = next;
    }
    function reset() {
        cpuAvailable = false; memoryAvailable = false; storageAvailable = false;
        cpuPercent = 0; memoryUsed = 0; memoryTotal = 0;
        storageUsed = 0; storageTotal = 0; storageFree = 0;
    }
    function numeric(value) { return typeof value === "number" && isFinite(value) && value >= 0; }
    function observedLine(line) {
        if (!active) return;
        try {
            const sample = JSON.parse(line);
            cpuAvailable = sample.cpuAvailable === true && numeric(sample.cpuPercent) && sample.cpuPercent <= 100;
            memoryAvailable = sample.memoryAvailable === true && numeric(sample.memoryUsed) && numeric(sample.memoryTotal)
                && sample.memoryTotal > 0 && sample.memoryUsed <= sample.memoryTotal;
            storageAvailable = sample.storageAvailable === true && numeric(sample.storageUsed) && numeric(sample.storageTotal)
                && numeric(sample.storageFree) && sample.storageTotal > 0 && sample.storageUsed <= sample.storageTotal && sample.storageFree <= sample.storageTotal;
            cpuPercent = cpuAvailable ? sample.cpuPercent : 0;
            memoryUsed = memoryAvailable ? sample.memoryUsed : 0; memoryTotal = memoryAvailable ? sample.memoryTotal : 0;
            storageUsed = storageAvailable ? sample.storageUsed : 0; storageTotal = storageAvailable ? sample.storageTotal : 0;
            storageFree = storageAvailable ? sample.storageFree : 0;
            error = typeof sample.error === "string" ? sample.error : "";
            if (!ready && !error) error = "Some system statistics are unavailable.";
            receivedSample = true;
            freshness.restart();
        } catch (parseError) {
            reset(); error = "System statistics could not be read.";
        }
    }
    function start() {
        if (!active) return;
        receivedSample = false;
        watcher.running = true;
        freshness.restart();
    }
    function retryObservation() {
        if (!active || retry.running) return;
        reset();
        if (!error) error = "System statistics are unavailable.";
        if (retryCount < 3) {
            retry.interval = 1000 * Math.pow(2, retryCount++);
            retry.restart();
        }
    }
    onActiveChanged: {
        retry.stop(); freshness.stop();
        stopping = true; watcher.running = false; stopping = false;
        reset(); error = ""; retryCount = 0;
        if (active) start();
    }
    Timer { id: retry; onTriggered: root.start() }
    Timer {
        id: freshness
        interval: 5500
        onTriggered: {
            if (!root.active) return;
            root.stopping = true; watcher.running = false; root.stopping = false;
            root.error = "System statistics stopped updating.";
            root.retryObservation();
        }
    }
    Process {
        id: watcher
        command: [typeof Desktop.controller === "string" ? Desktop.controller : "", "action", "system-stats-watch"]
        stdout: SplitParser { onRead: data => root.observedLine(data) }
        stderr: StdioCollector {}
        onExited: (code, status) => {
            freshness.stop();
            if (!root.stopping && root.active) root.retryObservation();
        }
    }
}
