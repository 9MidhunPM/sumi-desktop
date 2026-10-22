pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Networking as Net

Singleton {
    id: root
    readonly property var devices: Net.Networking.devices.values
    readonly property var wifiDevice: devices.find(device => device.type === Net.DeviceType.Wifi) || null
    readonly property bool wifiAvailable: wifiDevice !== null && Net.Networking.wifiHardwareEnabled
    readonly property bool wifiEnabled: Net.Networking.wifiEnabled
    readonly property var networks: wifiDevice ? wifiDevice.networks.values : []
    readonly property bool connected: devices.some(device => device.connected)
    readonly property string name: {
        const connectedWifi = networks.find(network => network.connected);
        if (connectedWifi) return connectedWifi.name;
        return devices.some(device => device.type === Net.DeviceType.Wired && device.connected) ? "Ethernet" : "Offline";
    }
    readonly property bool captivePortal: Net.Networking.connectivity === Net.NetworkConnectivity.Portal
    property bool discoveryRequested: false
    property var pendingNetwork: null
    property string connectionError: ""
    readonly property bool connecting: pendingNetwork !== null
    function syncDiscovery(): void { if (wifiDevice && !Desktop.preview) wifiDevice.scannerEnabled = discoveryRequested && wifiEnabled; }
    onDiscoveryRequestedChanged: syncDiscovery()
    onWifiDeviceChanged: syncDiscovery()
    onWifiEnabledChanged: syncDiscovery()
    onNetworksChanged: {
        if (pendingNetwork && networks.indexOf(pendingNetwork) < 0) {
            connectionError = "That network is no longer available. Select a network to retry.";
            pendingNetwork = null;
        }
    }
    Timer { id: connectionTimeout; interval: 45000; onTriggered: { root.connectionError = "Connection timed out. Check the password and try again."; root.pendingNetwork = null; } }
    Connections {
        target: root.pendingNetwork
        ignoreUnknownSignals: true
        function onConnectionFailed(reason) {
            root.connectionError = "Could not connect. Check the password and try again.";
            root.pendingNetwork = null;
            connectionTimeout.stop();
        }
        function onConnectedChanged() {
            if (root.pendingNetwork && root.pendingNetwork.connected) {
                root.pendingNetwork = null;
                root.connectionError = "";
                connectionTimeout.stop();
            }
        }
    }

    function toggleWifi(): void { if (!Desktop.preview) Net.Networking.wifiEnabled = !wifiEnabled; }
    function setScanning(value: bool): void { discoveryRequested = value; }
    function connect(network: var, psk: string): void {
        if (!network || Desktop.preview || connecting) return;
        root.pendingNetwork = network;
        root.connectionError = "";
        connectionTimeout.restart();
        if (psk && psk.length > 0) network.connectWithPsk(psk);
        else network.connect();
    }
    function disconnect(network: var): void { if (network && !Desktop.preview) network.disconnect(); }
    function forget(network: var): void { if (network && !Desktop.preview) network.forget(); }
}
