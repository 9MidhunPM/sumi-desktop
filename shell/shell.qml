//@ pragma UseQApplication
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "config"
import "services" as S
import "ThursdayNative" as ThursdayNative
import "CodexStatusModule" as CodexStatusModule

Scope {
    id: desktopRoot
    property string panel: ""
    property string settingsSection: ""
    property bool nativeDialogOpen: false
    property int activationSerial: 0
    property var activeScreen: Quickshell.screens.length ? Quickshell.screens[0] : null
    readonly property var widgetScreen: Quickshell.screens.find(s => s.name === "eDP-1")
        || Quickshell.screens.find(s => s.name.startsWith("eDP-"))
        || Quickshell.screens.find(s => s.name === "HDMI-A-1")
        || Quickshell.screens.slice().sort((a, b) => a.name.localeCompare(b.name))[0] || null
    readonly property var notificationScreen: {
        const focused = Hyprland.focusedMonitor;
        return Quickshell.screens.find(s => focused && s.name === focused.name) || Quickshell.screens[0] || null;
    }
    // Discovery belongs to the selected panel, never a fading cached instance.
    Binding { target: S.Network; property: "discoveryRequested"; value: desktopRoot.panel === "settings" && desktopRoot.settingsSection === "wifi" }
    Binding { target: S.Bluetooth; property: "discoveryRequested"; value: desktopRoot.panel === "settings" && desktopRoot.settingsSection === "bluetooth" }
    Connections {
        target: Quickshell
        function onScreensChanged() {
            if (Quickshell.screens.indexOf(desktopRoot.activeScreen) < 0) {
                desktopRoot.close();
                desktopRoot.activeScreen = desktopRoot.notificationScreen;
                desktopRoot.held = false;
            }
        }
    }
    property bool focusRunning: false
    property double focusDeadline: 0
    property double focusRemaining: 25 * 60 * 1000
    function focusStart() {
        if (focusRunning) return;
        if (focusRemaining <= 0) focusRemaining = 25 * 60 * 1000;
        focusDeadline = Date.now() + focusRemaining;
        focusRunning = true;
        focusTimer.interval = Math.max(1, focusRemaining);
        focusTimer.start();
    }
    function focusPause() {
        if (!focusRunning) return;
        focusRemaining = Math.max(0, focusDeadline - Date.now());
        focusRunning = false;
        focusTimer.stop();
    }
    function focusReset(minutes) {
        focusTimer.stop();
        focusRunning = false;
        focusDeadline = 0;
        focusRemaining = Math.max(1, Math.min(180, minutes)) * 60 * 1000;
    }
    Timer {
        id: focusTimer
        repeat: false
        onTriggered: {
            desktopRoot.focusRunning = false;
            desktopRoot.focusRemaining = 0;
            if (!desktopRoot.preview)
                Quickshell.execDetached(["notify-send", "--app-name=Sumi", "A focused moment", "Your session is complete. Take a breath."]);
        }
    }
    property bool held: false
    property bool manuallyHidden: false
    readonly property bool barVisible: Settings.barHiddenMode ? held : !manuallyHidden
    Binding { target: S.Spectrum; property: "displayEnabled"; value: desktopRoot.barVisible }
    readonly property bool preview: Quickshell.env("SUMI_PREVIEW") === "1"
    readonly property var codexStatus: codexLoader.item
    function resolveScreen(preferred) {
        if (preferred && Quickshell.screens.indexOf(preferred) >= 0) return preferred;
        const focused = Hyprland.focusedMonitor;
        return Quickshell.screens.find(s => focused && s.name === focused.name) || Quickshell.screens[0] || null;
    }
    function chooseScreen(preferred) { activeScreen = resolveScreen(preferred); }
    function open(name, screen) {
        if (nativeDialogOpen) return false;
        if (["launcher", "files", "clipboard", "appearance", "widgets", "settings", "calendar", "media", "notifications", "pomodoro", "help", "power"].indexOf(name) < 0) return false;
        chooseScreen(screen); if (!activeScreen) return false;
        if (name !== "settings") settingsSection = "";
        panel = name; activationSerial += 1;
        if (name === "notifications") S.Notifications.markRead();
        return true;
    }
    function openSettings(section, screen) { settingsSection = section || ""; open("settings", screen); }
    function toggle(name, screen) { if (panel === name && activeScreen === resolveScreen(screen)) close(); else open(name, screen); }
    function close() { if (nativeDialogOpen) return; panel = ""; settingsSection = ""; }
    function thursdayToggle() { if (nativeDialogOpen) return; close(); S.Desktop.action("ipc", ["thursday", "toggle"]); }
    function codexToggle(screen) { if (nativeDialogOpen) return; close(); if (codexLoader.item) codexLoader.item.toggleForScreen(screen); }
    IpcHandler {
        target: "sumi"
        function ping(): string { return "pong"; }
        function open(name: string): void { desktopRoot.open(name, null); }
        function toggle(name: string): void { desktopRoot.toggle(name, null); }
        function close(): void { desktopRoot.close(); }
        function status(): string { return JSON.stringify({panel: desktopRoot.panel, theme: Theme.id, preview: desktopRoot.preview, barVisible: desktopRoot.barVisible, applications: DesktopEntries.applications.values.length, notifications: S.Notifications.count, notificationPopups: S.Notifications.active.length, unread: S.Notifications.unread, dnd: Settings.dnd, wifi: S.Network.name, bluetoothEnabled: S.Bluetooth.enabled, volume: S.Audio.volume, muted: S.Audio.muted, battery: S.Battery.percent}); }
    }
    IpcHandler {
        target: "bar"
        function toggle(): void { if (Settings.barHiddenMode) desktopRoot.held = true; else desktopRoot.manuallyHidden = !desktopRoot.manuallyHidden; }
        function show(): void { desktopRoot.manuallyHidden = false; desktopRoot.held = true; }
        function hide(): void { desktopRoot.held = false; if (!Settings.barHiddenMode) desktopRoot.manuallyHidden = true; }
        function peek(): void { desktopRoot.held = true; }
        function release(): void { desktopRoot.held = false; }
    }
    IpcHandler { target: "launcher"; function toggle(): void { desktopRoot.toggle("launcher", null); } function files(): void { desktopRoot.toggle("files", null); } }
    IpcHandler { target: "notifications"; function toggle(): void { desktopRoot.toggle("notifications", null); } }
    IpcHandler { target: "appearance"; function toggle(): void { desktopRoot.toggle("appearance", null); } }
    IpcHandler {
        target: "widgets"
        function toggle(): void { desktopRoot.toggle("widgets", desktopRoot.widgetScreen); }
        function status(): string { return JSON.stringify({screen: desktopRoot.widgetScreen ? desktopRoot.widgetScreen.name : "", imageKey: S.Widgets.scene.imageKey, layout: S.Widgets.layoutMode, enabled: S.Widgets.document.enabled, mediaAvailable: S.WidgetMedia.available, musicPlaying: S.Media.playing, spectrumActive: S.Spectrum.active, onBattery: S.Battery.onBattery, progressActive: S.WidgetMedia.progressActive, saving: S.Widgets.saving, visible: widgetSurface.visible, idle: widgetSurface.idle, fullscreen: widgetSurface.occluded, moving: widgetSurface.moving, geometry: widgetSurface.geometry, error: S.Widgets.error}); }
    }
    IpcHandler { target: "settings"; function toggle(): void { desktopRoot.toggle("settings", null); } }
    IpcHandler { target: "clipboard"; function toggle(): void { desktopRoot.toggle("clipboard", null); } }
    // Native assistant integration begins.
    LazyLoader {
        id: thursdayLoader
        active: !desktopRoot.preview
        component: ThursdayNative.Thursday {
            id: thursday
            repoRoot: ""
            theme: Theme
            // The integration also receives its backend's local preference.
            // Re-apply the desktop preference without editing external code.
            onReducedMotionChanged: if (reducedMotion !== Theme.effectiveReducedMotion) Qt.callLater(() => { thursday.reducedMotion = Theme.effectiveReducedMotion; })
            Connections { target: Theme; function onEffectiveReducedMotionChanged() { thursday.reducedMotion = Theme.effectiveReducedMotion; } }
            Component.onCompleted: reducedMotion = Theme.effectiveReducedMotion
        }
    }
    LazyLoader { id: codexLoader; active: !desktopRoot.preview; component: CodexStatusModule.CodexStatus { theme: Theme; reducedMotion: Theme.effectiveReducedMotion } }
    // Native assistant integration ends.
    Variants { model: Quickshell.screens; Bar { app: desktopRoot } }
    Variants { model: Quickshell.screens; Overlay { app: desktopRoot } }
    DesktopWidgets { id: widgetSurface; modelData: desktopRoot.widgetScreen; app: desktopRoot }
    NotificationToasts { app: desktopRoot }
}
