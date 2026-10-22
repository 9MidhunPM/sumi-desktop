pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.UPower as Up

Singleton {
    id: root
    readonly property bool battery: !Settings.fullMotion && (Up.UPower.onBattery || Up.PowerProfiles.profile === Up.PowerProfile.PowerSaver)
    readonly property string mode: Settings.reducedMotion ? "reduced" : battery ? "battery" : "normal"
    readonly property bool reduced: mode === "reduced"
    readonly property bool expressive: mode === "normal"
    readonly property int enter: reduced ? 0 : battery ? 140 : 360
    readonly property int exit: reduced ? 0 : battery ? 110 : 200
    readonly property int control: reduced ? 0 : battery ? 80 : 180
    property string appliedMode: ""
    property string error: ""
    property int retryCount: 0
    function synchronize(): void {
        if (Settings.loading || Quickshell.env("SUMI_PREVIEW") === "1" || apply.running || appliedMode === mode) return;
        apply.requestedMode = mode;
        apply.command = [Quickshell.env("SUMI_DESKTOPCTL") || Quickshell.env("HOME") + "/.local/bin/desktopctl", "motion", "apply", mode, "--json"];
        apply.running = true;
    }
    onModeChanged: { retryCount = 0; Qt.callLater(synchronize); }
    Timer { id: retry; interval: 1000; onTriggered: root.synchronize() }
    Connections { target: Settings; function onLoadingChanged() { Qt.callLater(root.synchronize); } }
    Component.onCompleted: Qt.callLater(synchronize)
    Process {
        id: apply
        property string requestedMode: ""
        stdout: StdioCollector {}
        stderr: StdioCollector { id: errors }
        onExited: (code, status) => {
            if (code === 0) { root.appliedMode = requestedMode; root.error = ""; root.retryCount = 0; }
            else if (/already running|interrupted desktop|pending recovery/i.test(errors.text) && root.retryCount++ < 20) retry.restart();
            else root.error = errors.text.trim() || "Desktop motion could not be updated.";
            if (requestedMode !== root.mode) Qt.callLater(root.synchronize);
        }
    }
}
