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
    readonly property int enter: reduced ? 0 : battery ? 120 : 160
    readonly property int exit: reduced ? 0 : battery ? 80 : 100
    readonly property int control: reduced ? 0 : battery ? 60 : 90
    // Shell-local roles. Keep compositor synchronization and legacy timings intact.
    readonly property int content: reduced ? 0 : battery ? 80 : 140
    readonly property int music: reduced ? 0 : battery ? 100 : 180
    readonly property int geometry: reduced ? 0 : battery ? 120 : 280
    // Island contour springs: response is the undamped period in seconds and
    // damping the ratio. Growth overshoots playfully; settling never undershoots.
    readonly property real springResponse: battery ? 0.34 : 0.46
    readonly property real springDamping: battery ? 0.84 : 0.66
    readonly property real settleResponse: battery ? 0.26 : 0.34
    readonly property real settleDamping: 1
    // Content sharpens in just behind the contour's leading edge and leaves first.
    readonly property int reveal: reduced ? 0 : battery ? 160 : 300
    readonly property int conceal: reduced ? 0 : battery ? 80 : 120
    readonly property int revealDelay: reduced || battery ? 0 : 40
    // Blur and cast shadows are reserved for full motion on accelerated renderers.
    readonly property bool depthEffects: expressive
    // One motion language for every surface. Arrivals use the bounce curve, a
    // single soft overshoot (~7%) that matches the island's springs; exits are
    // brisk and never overshoot; fades and colour changes use the standard curve.
    readonly property int bounce: reduced ? 0 : battery ? 240 : 420
    readonly property var bounceCurve: battery ? standardCurve : [0.32, 1.48, 0.58, 1, 1, 1]
    readonly property var standardCurve: [0.2, 0, 0, 1, 1, 1]
    readonly property var exitCurve: [0.3, 0, 0.6, 1, 1, 1]
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
