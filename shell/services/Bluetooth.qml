pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Bluetooth as Bt
import Quickshell.Io

Singleton {
    id: root
    readonly property var adapter: Bt.Bluetooth.defaultAdapter
    readonly property var devices: adapter && adapter.devices ? adapter.devices.values || [] : []
    readonly property var sortedDevices: devices.filter(device => !!device).sort((a, b) => {
        const rank = device => device.connected ? 0 : device.paired ? 1 : 2;
        return rank(a) - rank(b) || String(a.name || a.address || "").localeCompare(String(b.name || b.address || ""));
    })
    readonly property bool available: !!adapter
    readonly property bool enabled: !!adapter && adapter.enabled === true
    readonly property bool scanning: !!adapter && adapter.discovering === true
    readonly property int connectedCount: devices.filter(device => device && device.connected === true).length
    property bool discoveryRequested: false
    function syncDiscovery(): void { if (adapter && !Desktop.preview) adapter.discovering = discoveryRequested && enabled; }
    onDiscoveryRequestedChanged: syncDiscovery()
    onAdapterChanged: syncDiscovery()
    onEnabledChanged: syncDiscovery()

    function toggle(): void { if (adapter && !Desktop.preview) adapter.enabled = !adapter.enabled; }
    function setScanning(value: bool): void { discoveryRequested = value; }
    function connectDevice(device: var): void { if (device && !Desktop.preview) device.connected = true; }
    function disconnectDevice(device: var): void { if (device && !Desktop.preview) device.connected = false; }
    property bool pairing: false
    property string pairingName: ""
    property string pairingAddress: ""
    property string pairingError: ""
    property string promptKind: ""
    property string promptValue: ""
    property int promptId: 0
    property int passkeyEntered: 0
    function pairDevice(device: var): void {
        if (!device || Desktop.preview || pairing) return;
        pairingAddress = device.address;
        pairingName = device.name || device.address;
        pairingError = ""; promptKind = ""; pairing = true;
        helper.running = true;
    }
    function answerPairing(value: var): void {
        if (pairing && helper.running) helper.write(JSON.stringify({command: "respond", prompt: promptId, value: value}) + "\n");
    }
    function cancelPairing(): void {
        if (helper.running) helper.write(JSON.stringify({command: "cancel"}) + "\n");
    }
    function openManager(): void { Desktop.action("bluetooth-manager", []); }
    Process {
        id: helper
        command: ["python3", Quickshell.env("SUMI_BLUETOOTH_AGENT") || Quickshell.shellPath("../lib/sumi/bluetooth_agent.py"), root.pairingAddress]
        stdinEnabled: true
        stdout: SplitParser {
            onRead: line => {
                try {
                    const event = JSON.parse(line);
                    if (event.type === "done") { root.pairing = false; root.promptKind = ""; root.pairingError = event.error || ""; }
                    else if (event.type === "prompt") { root.promptKind = event.kind; root.promptValue = String(event.value || ""); root.promptId = event.prompt; root.passkeyEntered = event.entered || 0; }
                    else if (event.type === "validation") root.pairingError = event.error;
                    else if (event.type === "waiting") { root.promptKind = ""; root.pairingError = ""; }
                } catch (error) { root.pairingError = "Could not read the Bluetooth pairing response."; }
            }
        }
        stderr: StdioCollector { id: helperErrors }
        onExited: (code, status) => {
            if (root.pairing) root.pairingError = helperErrors.text.trim() || "Pairing ended before the device connected. Try again.";
            root.pairing = false; root.promptKind = "";
        }
    }
}
