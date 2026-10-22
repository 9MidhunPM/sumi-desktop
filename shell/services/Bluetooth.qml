pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Bluetooth as Bt

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
    // BlueZ pairing needs an authentication agent; use the installed manager so
    // PIN/passkey confirmation remains visible and interactive.
    function pairDevice(device: var): void { if (device) Desktop.action("bluetooth-manager", []); }
    function openManager(): void { Desktop.action("bluetooth-manager", []); }
}
