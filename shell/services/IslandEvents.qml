pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Hyprland as H

// Presentation state only: Notifications remains the sole owner of native
// notification expiry, actions and history. Pending previews retain deadlines.
Singleton {
    id: root
    property bool displayEnabled: true
    property var fullscreenScreens: []
    property var availableScreens: Quickshell.screens.map(screen => screen.name).filter(name => name.length > 0)
    property int sequence: 0
    property string focusedScreenName: H.Hyprland.focusedMonitor ? H.Hyprland.focusedMonitor.name : ""
    property var current: null
    property var pending: []
    readonly property string eventKind: current ? current.kind : ""
    readonly property string eventLabel: current ? current.label : ""
    readonly property real eventValue: current ? current.value : 0
    readonly property string eventScreenName: current ? current.screen : ""
    readonly property real expiresAt: current ? current.deadline : 0
    readonly property bool active: current !== null
    readonly property int eventPriority: current ? current.priority : 0
    readonly property bool eventCritical: current ? current.critical : false
    readonly property string eventSection: current ? current.section : "home"
    readonly property var notification: current && current.notificationId !== null
        ? Notifications.history.find(entry => entry.id === current.notificationId) || null : null
    readonly property int pendingCount: pending.length
    readonly property bool criticalAttention: (Battery.available && Battery.onBattery && !Battery.charging && Battery.percent <= 5)
        || (!Notifications.dnd && Notifications.history.some(entry => entry.popup && entry.critical && !!Notifications.live[entry.id]))
    property bool audioArmed: false
    property bool batteryArmed: false
    property bool brightnessArmed: false
    property bool connectivityArmed: false
    property real previousVolume: 0
    property bool previousMuted: false
    property bool previousSourceMuted: false
    property real previousBrightness: 0
    property bool previousOnBattery: false
    property bool previousCharging: false
    property bool warned20: false
    property bool warned10: false
    property bool warned5: false
    property string previousNetwork: ""
    property bool previousBluetooth: false
    property int previousBluetoothCount: 0

    function clear(): void {
        expiry.stop();
        current = null;
        pending = [];
    }
    function resolveScreen(name) {
        if (availableScreens.indexOf(name) >= 0) return name;
        return availableScreens.indexOf(focusedScreenName) >= 0 ? focusedScreenName : availableScreens[0] || "";
    }
    function reroute() {
        if (current) current = Object.assign({}, current, {screen: resolveScreen(current.screen)});
        pending = pending.map(event => Object.assign({}, event, {screen: resolveScreen(event.screen)}));
        reconcile();
    }
    function allowed(event) {
        return displayEnabled && event.screen.length > 0 && (event.critical || fullscreenScreens.indexOf(event.screen) < 0);
    }
    function liveNotification(event) {
        return event.notificationId === null || (!Notifications.dnd && !!Notifications.live[event.notificationId]
            && Notifications.history.some(entry => entry.id === event.notificationId && entry.popup));
    }
    function valid(event) { return allowed(event) && event.deadline > Date.now() && liveNotification(event); }
    function activate(event) {
        current = event;
        expiry.interval = Math.max(1, event.deadline - Date.now());
        expiry.restart();
    }
    function prunePending() {
        pending = pending.filter(event => valid(event)).sort((a, b) => b.priority - a.priority || a.order - b.order).slice(0, 3);
    }
    function advance() {
        expiry.stop(); current = null;
        prunePending();
        if (pending.length) {
            const next = pending[0]; pending = pending.slice(1); activate(next);
        }
    }
    function queue(event) {
        pending = pending.filter(item => item.notificationId !== event.notificationId).concat([event]);
        prunePending();
    }
    function defaults(kind) {
        if (kind === "critical-battery") return {priority: 100, critical: true, section: "controls"};
        if (kind === "low-battery" || kind === "focus-complete" || kind === "error")
            return {priority: 80, critical: false, section: kind === "focus-complete" ? "home" : "controls"};
        if (kind === "notification") return {priority: 60, critical: false, section: "inbox"};
        if (kind === "network" || kind === "bluetooth") return {priority: 20, critical: false, section: "controls"};
        return {priority: 40, critical: false, section: "controls"};
    }
    // Existing positional API is retained. options adds presentation metadata.
    function show(kind, label, value, durationMs, screenName = "", options = {}) {
        const base = defaults(kind);
        const event = {kind: kind, label: String(label || ""), value: Math.max(0, Math.min(1, Number(value) || 0)),
            screen: resolveScreen(screenName || focusedScreenName), priority: options.priority === undefined ? base.priority : options.priority,
            critical: options.critical === undefined ? base.critical : options.critical,
            section: options.section || base.section, notificationId: options.notificationId === undefined ? null : options.notificationId,
            created: Date.now(), order: ++sequence, deadline: Date.now() + Math.max(1, Number(durationMs) || 1)};
        if (!valid(event)) return;
        if (!current || !valid(current)) { activate(event); return; }
        if (current.notificationId !== null && current.notificationId === event.notificationId) {
            // Replacements update the same preview without extending its age.
            event.deadline = current.deadline; event.created = current.created; event.order = current.order; activate(event); return;
        }
        if (event.priority > current.priority || (event.priority === current.priority && event.notificationId === null)) {
            if (current.notificationId !== null) queue(current);
            activate(event);
        } else if (event.notificationId !== null) queue(event);
        // Lower-priority OSD/connectivity feedback is deliberately not queued.
    }
    function dismissCurrent(): void {
        const id = current ? current.notificationId : null;
        if (id !== null) Notifications.dismissPopup(id);
        else advance();
    }
    function publishFocusComplete(screenName = "") { show("focus-complete", "Focus complete", 1, 5000, screenName); }
    function received(entry) {
        if (!entry.popup || Notifications.dnd || !Notifications.live[entry.id]) return;
        show("notification", entry.summary || entry.appName, 0, entry.critical ? 8000 : 6000, "",
            {notificationId: entry.id, critical: entry.critical, priority: entry.critical ? 100 : 60, section: "inbox"});
    }
    function refreshed(event) {
        if (event.notificationId === null) return event;
        const entry = Notifications.history.find(item => item.id === event.notificationId);
        if (!entry) return event;
        return Object.assign({}, event, {label: entry.summary || entry.appName, critical: entry.critical, priority: entry.critical ? 100 : 60});
    }
    function syncNotifications() {
        pending = pending.map(event => refreshed(event));
        if (current) current = refreshed(current);
        reconcile();
    }
    function reconcile() {
        prunePending();
        if (current && !valid(current)) advance();
        else if (pending.length && (!current || pending[0].priority > current.priority)) {
            const next = pending[0]; pending = pending.slice(1);
            if (current && current.notificationId !== null) queue(current);
            activate(next);
        }
    }
    onDisplayEnabledChanged: if (!displayEnabled) clear()
    onFullscreenScreensChanged: reconcile()
    onAvailableScreensChanged: reroute()
    Timer { id: expiry; onTriggered: root.advance() }
    Connections {
        target: Notifications
        function onReceived(entry) { root.received(entry); }
        function onHistoryChanged() { root.syncNotifications(); }
        function onDndChanged() { root.syncNotifications(); }
    }

    function armAudio(): void {
        audioArmed = Audio.ready;
        previousVolume = Audio.volume; previousMuted = Audio.muted; previousSourceMuted = Audio.sourceMuted;
    }
    function audioChanged(): void {
        if (!Audio.ready || !audioArmed) { armAudio(); return; }
        const microphoneChanged = previousSourceMuted !== Audio.sourceMuted;
        const outputChanged = previousMuted !== Audio.muted || Math.abs(previousVolume - Audio.volume) > 0.0001;
        previousVolume = Audio.volume; previousMuted = Audio.muted; previousSourceMuted = Audio.sourceMuted;
        if (microphoneChanged && Audio.hasInput)
            show("microphone", Audio.sourceMuted ? "Mic muted" : "Mic on", Audio.sourceMuted ? 0 : 1, 1500);
        else if (outputChanged && Audio.hasOutput)
            show("volume", Audio.muted ? "Muted" : Math.round(Audio.volume * 100) + "%", Audio.muted ? 0 : Audio.volume, 1500);
    }
    function audioAvailabilityChanged(): void { audioArmed = false; audioSettle.restart(); }
    Timer { id: audioSettle; interval: 500; onTriggered: root.armAudio() }
    Connections {
        target: Audio
        function onReadyChanged() { root.audioAvailabilityChanged(); }
        function onHasOutputChanged() { root.audioAvailabilityChanged(); }
        function onHasInputChanged() { root.audioAvailabilityChanged(); }
        function onVolumeChanged() { if (root.audioArmed) root.audioChanged(); }
        function onMutedChanged() { if (root.audioArmed) root.audioChanged(); }
        function onSourceMutedChanged() { if (root.audioArmed) root.audioChanged(); }
    }
    function armBrightness() {
        brightnessArmed = Brightness.ready && Brightness.available;
        previousBrightness = Brightness.percent;
    }
    Connections {
        target: Brightness
        function onReadyChanged() { root.armBrightness(); }
        function onAvailableChanged() { root.armBrightness(); }
        function onChanged(value) {
            if (!Brightness.ready || !Brightness.available) return;
            root.previousBrightness = value;
            root.show("brightness", Math.round(value) + "%", value / 100, 1500);
        }
    }
    function armBattery(): void {
        batteryArmed = Battery.available;
        previousOnBattery = Battery.onBattery; previousCharging = Battery.charging;
        // Low battery on shell startup sets attention, never an intrusive preview.
        warned20 = Battery.onBattery && Battery.percent <= 20;
        warned10 = Battery.onBattery && Battery.percent <= 10;
        warned5 = Battery.onBattery && Battery.percent <= 5;
    }
    function batteryChanged(): void {
        if (!batteryArmed || !Battery.available) return;
        const powerChanged = previousOnBattery !== Battery.onBattery;
        const startedCharging = !previousCharging && Battery.charging;
        previousOnBattery = Battery.onBattery; previousCharging = Battery.charging;
        if (!Battery.onBattery || Battery.charging || Battery.percent >= 23) warned20 = false;
        if (!Battery.onBattery || Battery.charging || Battery.percent >= 13) warned10 = false;
        if (!Battery.onBattery || Battery.charging || Battery.percent >= 8) warned5 = false;
        if (!Battery.onBattery || Battery.charging) {
            if (current && (eventKind === "critical-battery" || eventKind === "low-battery")) advance();
        }
        if (powerChanged || startedCharging)
            show("power", Battery.onBattery ? "On battery" : Battery.charging ? "Charging" : "AC power", Battery.percent / 100, 3000);
        if (Battery.onBattery && !Battery.charging) {
            if (Battery.percent <= 5 && !warned5) {
                warned5 = true; warned10 = true; warned20 = true;
                show("critical-battery", Math.round(Battery.percent) + "% battery", Battery.percent / 100, 8000);
            } else if (Battery.percent <= 10 && !warned10) {
                warned10 = true; warned20 = true;
                show("low-battery", Math.round(Battery.percent) + "% battery", Battery.percent / 100, 5000);
            } else if (Battery.percent <= 20 && !warned20) {
                warned20 = true;
                show("low-battery", Math.round(Battery.percent) + "% battery", Battery.percent / 100, 5000);
            }
        }
    }
    Timer { id: batterySettle; interval: 500; onTriggered: root.armBattery() }
    Connections {
        target: Battery
        function onAvailableChanged() { root.batteryArmed = false; batterySettle.restart(); }
        function onOnBatteryChanged() { root.batteryChanged(); }
        function onChargingChanged() { root.batteryChanged(); }
        function onPercentChanged() { root.batteryChanged(); }
    }
    function armConnectivity() {
        previousNetwork = Network.name;
        previousBluetooth = Bluetooth.enabled; previousBluetoothCount = Bluetooth.connectedCount;
        connectivityArmed = true;
    }
    Timer { id: connectivitySettle; interval: 1000; onTriggered: root.armConnectivity() }
    Connections {
        target: Network
        function onNameChanged() {
            if (!root.connectivityArmed) return;
            if (Network.name !== root.previousNetwork) {
                root.previousNetwork = Network.name;
                root.show("network", Network.connected ? "Connected · " + Network.name : "Disconnected", Network.connected ? 1 : 0, 2500);
            }
        }
    }
    Connections {
        target: Bluetooth
        function onEnabledChanged() {
            if (!root.connectivityArmed) return;
            root.previousBluetooth = Bluetooth.enabled;
            root.show("bluetooth", Bluetooth.enabled ? "Bluetooth on" : "Bluetooth off", Bluetooth.enabled ? 1 : 0, 2500);
        }
        function onConnectedCountChanged() {
            if (!root.connectivityArmed || Bluetooth.connectedCount === root.previousBluetoothCount) return;
            root.previousBluetoothCount = Bluetooth.connectedCount;
            root.show("bluetooth", Bluetooth.connectedCount ? "Bluetooth · " + Bluetooth.connectedCount + " connected" : "Bluetooth disconnected", Bluetooth.connectedCount ? 1 : 0, 2500);
        }
    }
    Component.onCompleted: { audioSettle.start(); batterySettle.start(); armBrightness(); connectivitySettle.start(); }
}
