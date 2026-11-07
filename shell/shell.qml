//@ pragma UseQApplication
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "config"
import "services" as S
import "integrations" as ThursdayNative

// The island hosts daily controls, short-gesture navigation and Thursday output.
Scope {
    id: desktopRoot
    property string panel: ""
    property string settingsSection: ""
    property bool nativeDialogOpen: false
    property bool captureSelecting: false
    property int activationSerial: 0
    property var islandWindows: []
    readonly property var thursdayBackend: thursdayLoader.item
    property bool thursdayExternal: false
    property string thursdayError: ""
    function updateThursdayError() {
        const backend = thursdayBackend;
        const message = backend ? backend.errorText || backend.voiceError || backend.speechError || backend.outputNotice || "" : "";
        if (message === thursdayError) return;
        const previous = thursdayError;
        thursdayError = message;
        if (message && !thursdayExternal) S.IslandEvents.show("thursday", message, 0, 8000, "", {priority: 80, section: "thursday"});
        else if (!message && S.IslandEvents.eventKind === "thursday" && S.IslandEvents.eventLabel === previous) S.IslandEvents.dismissCurrent();
    }
    property double thursdayOutputUntil: 0
    property string thursdayOutputScreen: ""
    readonly property bool thursdayOutputActive: !!thursdayBackend && !!thursdayBackend.latestAnswer && !thursdayExternal
        && (thursdayBackend.busy || thursdayBackend.speaking || thursdayBackend.playbackRunning || thursdayBackend.speechPreparing || thursdayOutputUntil > 0)
    function holdThursdayOutput() {
        const backend = thursdayBackend;
        if (!backend || !backend.latestAnswer) return;
        if (!thursdayOutputScreen) {
            const screen = resolveScreen(backend.currentScreen);
            thursdayOutputScreen = screen ? screen.name : "";
        }
        thursdayOutputUntil = Date.now() + 8000;
        thursdayReading.restart();
    }
    Timer { id: thursdayReading; interval: 8000; onTriggered: desktopRoot.thursdayOutputUntil = 0 }
    function openThursdayFull() {
        if (!thursdayBackend || nativeDialogOpen) return;
        close();
        thursdayBackend.openChat();
    }
    function suppressThursdayHud() {
        if (thursdayBackend && !thursdayExternal && !thursdayBackend.hudDismissed) thursdayBackend.hudDismissed = true;
    }
    onThursdayBackendChanged: Qt.callLater(suppressThursdayHud)
    Connections {
        target: desktopRoot.thursdayBackend
        function onOpenedChanged() {
            const backend = desktopRoot.thursdayBackend;
            if (!backend) return;
            if (!backend.opened) { desktopRoot.thursdayExternal = false; return; }
            if (desktopRoot.thursdayExternal) return;
            backend.opened = false;
            desktopRoot.openIsland("thursday", null, true);
        }
        function onErrorTextChanged() { desktopRoot.updateThursdayError(); }
        function onVoiceErrorChanged() { desktopRoot.updateThursdayError(); }
        function onSpeechErrorChanged() { desktopRoot.updateThursdayError(); }
        function onOutputNoticeChanged() { desktopRoot.updateThursdayError(); }
        function onHudDismissedChanged() { desktopRoot.suppressThursdayHud(); }
        function onConfirmationsChanged() {
            const backend = desktopRoot.thursdayBackend;
            if (backend && backend.confirmations.length && !desktopRoot.thursdayExternal)
                S.IslandEvents.show("thursday", "Thursday needs your approval", 1, 8000, "", {priority: 80, section: "thursday"});
            else if (S.IslandEvents.eventKind === "thursday" && S.IslandEvents.eventLabel === "Thursday needs your approval")
                S.IslandEvents.dismissCurrent();
        }
        function onBusyChanged() { if (desktopRoot.thursdayBackend && !desktopRoot.thursdayBackend.busy) desktopRoot.holdThursdayOutput(); }
        function onLatestAnswerChanged() {
            if (!desktopRoot.thursdayBackend || !desktopRoot.thursdayBackend.latestAnswer) {
                desktopRoot.thursdayOutputUntil = 0;
                desktopRoot.thursdayOutputScreen = "";
                thursdayReading.stop();
            } else desktopRoot.holdThursdayOutput();
        }
        function onSpeakingChanged() { desktopRoot.holdThursdayOutput(); }
        function onSpeechPreparingChanged() { desktopRoot.holdThursdayOutput(); }
    }
    function registerIsland(window) { islandWindows = islandWindows.concat([window]); }
    function unregisterIsland(window) { islandWindows = islandWindows.filter(candidate => candidate !== window); }
    function dismissIslands(except, restoreApplication = false) {
        islandWindows.forEach(window => { if (window && window !== except) window.dismiss(restoreApplication); });
    }
    function openIsland(section, preferred, toggle) {
        if (nativeDialogOpen) return;
        if (thursdayBackend && thursdayBackend.opened) thursdayBackend.opened = false;
        const screen = resolveScreen(preferred);
        if (section === "thursday" && thursdayBackend) {
            if (screen) thursdayBackend.currentScreen = screen;
            thursdayBackend.connectHelper();
        }
        const window = islandWindows.find(candidate => candidate && candidate.modelData === screen);
        if (!window) return;
        if (window.pinned) {
            if (toggle && window.section === section) window.dismiss(true);
            else window.selectSection(section || "controls");
            return;
        }
        close();
        Qt.callLater(() => {
            if (window && islandWindows.indexOf(window) >= 0) window.pin(section || "controls");
        });
    }
    function toggleIsland() { openIsland("controls", null, true); }
    function selectCapture(annotate, record) {
        if (nativeDialogOpen) return;
        close();
        captureSelecting = true;
        nativeDialogOpen = true;
        selectorDelay.generation += 1;
        selectorDelay.annotate = annotate;
        selectorDelay.record = record;
        selectorDelay.restart();
    }
    function finishCapture(generation, error) {
        if (!captureSelecting || generation !== selectorDelay.generation) return;
        captureSelecting = false;
        nativeDialogOpen = false;
        if (error) Qt.callLater(() => S.IslandEvents.show("error", error, 0, 8000));
    }
    function releaseCompletedCapture() {
        if (captureSelecting && !selectorDelay.running && S.Desktop.pendingCount === 0 && !S.Recording.busy)
            finishCapture(selectorDelay.generation, "");
    }
    Connections {
        target: S.Desktop
        function onPendingCountChanged() { Qt.callLater(desktopRoot.releaseCompletedCapture); }
    }
    Connections {
        target: S.Recording
        function onBusyChanged() { Qt.callLater(desktopRoot.releaseCompletedCapture); }
    }
    Timer {
        id: selectorDelay
        // Compact the dashboard and release its input before slurp starts.
        interval: 80
        property bool annotate: false
        property bool record: false
        property int generation: 0
        onTriggered: {
            const token = generation;
            const done = function(ok, result, error) { desktopRoot.finishCapture(token, ok ? "" : error); };
            try {
                if (record) S.Recording.start(done);
                else S.Desktop.action("capture", annotate ? ["region", "annotate"] : ["region"], done);
            } catch (error) { desktopRoot.finishCapture(token, String(error)); }
        }
    }
    property var activeScreen: Quickshell.screens.length ? Quickshell.screens[0] : null
    readonly property var widgetScreen: Quickshell.screens.find(s => s.name === Quickshell.env("SUMI_WIDGET_SCREEN"))
        || Quickshell.screens[0] || null
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
    property double focusDuration: 25 * 60 * 1000
    function focusStart() {
        if (focusRunning) return;
        if (focusRemaining <= 0) { focusRemaining = 25 * 60 * 1000; focusDuration = focusRemaining; }
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
        focusDuration = focusRemaining;
    }
    Timer {
        id: focusTimer
        repeat: false
        onTriggered: {
            desktopRoot.focusRunning = false;
            desktopRoot.focusRemaining = 0;
            S.IslandEvents.publishFocusComplete();
        }
    }
    property bool held: false
    property bool manuallyHidden: false
    readonly property bool barVisible: Settings.barHiddenMode ? held : !manuallyHidden
    Binding { target: S.Spectrum; property: "displayEnabled"; value: desktopRoot.barVisible }
    Binding { target: S.Spectrum; property: "playbackActive"; value: S.IslandMedia.playing }
    Binding {
        target: S.IslandEvents
        property: "displayEnabled"
        value: desktopRoot.barVisible && desktopRoot.panel === "" && !desktopRoot.nativeDialogOpen
            && !desktopRoot.islandWindows.some(window => window.modelData === desktopRoot.notificationScreen && window.idle)
    }
    Binding {
        target: S.IslandEvents
        property: "fullscreenScreens"
        value: Hyprland.monitors.values.filter(monitor => monitor.activeWorkspace && monitor.activeWorkspace.hasFullscreen).map(monitor => monitor.name)
    }
    Connections {
        target: S.Desktop
        function onLastErrorChanged() {
            if (S.Desktop.lastError) S.IslandEvents.show("error", S.Desktop.lastError, 0, 8000);
        }
    }
    Connections {
        target: S.Recording
        function onCompleted(operation, result) {
            Qt.callLater(() => S.IslandEvents.show("recording", operation === "start" ? "Recording started" : "Recording saved", operation === "start" ? 1 : 0, 3000, "", {section: "controls"}));
        }
    }
    readonly property bool preview: Quickshell.env("SUMI_PREVIEW") === "1"
    readonly property var codexStatus: null
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
        dismissIslands();
        if (name !== "settings") settingsSection = "";
        panel = name; activationSerial += 1;
        if (name === "notifications") S.Notifications.markRead();
        return true;
    }
    function openSettings(section, screen) { settingsSection = section || ""; open("settings", screen); }
    function toggle(name, screen) { if (panel === name && activeScreen === resolveScreen(screen)) close(); else open(name, screen); }
    function close() { if (nativeDialogOpen) return; dismissIslands(); panel = ""; settingsSection = ""; }
    function thursdayToggle() { openIsland("thursday", null, true); }
    function codexToggle(screen) {}
    function launcherReady(): bool {
        const instances = overlays.instances;
        if (!Quickshell.screens.length || instances.length !== Quickshell.screens.length) return false;
        for (let i = 0; i < instances.length; i++)
            if (!instances[i].launcherReady) return false;
        return true;
    }
    // One registration per session, never per monitor or preview instance.
    LazyLoader {
        active: !desktopRoot.preview
        component: Scope {
            GlobalShortcut { appid: "sumi"; name: "launcher"; description: "Open command hub"; onPressed: desktopRoot.toggle("launcher", null) }
            GlobalShortcut { appid: "sumi"; name: "files"; description: "Find files"; onPressed: desktopRoot.toggle("files", null) }
            GlobalShortcut { appid: "sumi"; name: "notifications"; description: "Island Inbox"; onPressed: desktopRoot.openIsland("inbox", null, true) }
            GlobalShortcut { appid: "sumi"; name: "appearance"; description: "Appearance"; onPressed: desktopRoot.toggle("appearance", null) }
            GlobalShortcut { appid: "sumi"; name: "clipboard"; description: "Clipboard history"; onPressed: desktopRoot.toggle("clipboard", null) }
            GlobalShortcut { appid: "sumi"; name: "help"; description: "Shortcut reference"; onPressed: desktopRoot.toggle("help", null) }
        }
    }
    IpcHandler {
        target: "sumi"
        function ping(): string { return desktopRoot.launcherReady() ? "pong" : "starting"; }
        function open(name: string): void { desktopRoot.open(name, null); }
        function toggle(name: string): void { desktopRoot.toggle(name, null); }
        function close(): void { desktopRoot.close(); }
        function status(): string { return JSON.stringify({panel: desktopRoot.panel, theme: Theme.id, preview: desktopRoot.preview, barVisible: desktopRoot.barVisible, nativeDialogOpen: desktopRoot.nativeDialogOpen, captureSelecting: desktopRoot.captureSelecting, recording: S.Recording.recording, recordingBusy: S.Recording.busy, applications: DesktopEntries.applications.values.length, notifications: S.Notifications.count, notificationPopups: S.Notifications.active.length, unread: S.Notifications.unread, dnd: Settings.dnd, wifi: S.Network.name, bluetoothEnabled: S.Bluetooth.enabled, volume: S.Audio.volume, muted: S.Audio.muted, battery: S.Battery.percent}); }
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
    IpcHandler { target: "notifications"; function toggle(): void { desktopRoot.openIsland("inbox", null, true); } }
    IpcHandler { target: "appearance"; function toggle(): void { desktopRoot.toggle("appearance", null); } }
    IpcHandler {
        target: "island"
        function toggle(): void { desktopRoot.toggleIsland(); }
        function open(section: string): void { desktopRoot.openIsland(section, null, false); }
        function close(): void { desktopRoot.dismissIslands(null, true); }
        function setNotch(enabled: bool): void { Settings.setValue("islandNotch", enabled); }
        function status(): string {
            return JSON.stringify(desktopRoot.islandWindows.map(window => ({screen: window.modelData ? window.modelData.name : "", notch: window.notch,
                section: window.section, alert: window.eventHere ? S.IslandEvents.eventKind : "", critical: window.eventHere && S.IslandEvents.eventCritical, pending: S.IslandEvents.pendingCount, assistantConnected: !!desktopRoot.thursdayBackend && desktopRoot.thursdayBackend.connected, assistantReady: !!desktopRoot.thursdayBackend && desktopRoot.thursdayBackend.ready, assistantActive: window.assistantActive, assistantOutput: window.assistantOutputHere, visible: window.visible, pinned: window.pinned, expanded: window.expanded, activity: window.activity,
                idle: window.idle, bodyWidth: window.bodyWidth, bodyHeight: window.bodyHeight, spectrum: window.spectrumDemand})));
        }
    }
    IpcHandler {
        target: "widgets"
        function toggle(): void { desktopRoot.toggle("widgets", desktopRoot.widgetScreen); }
        function status(): string { return JSON.stringify({screen: desktopRoot.widgetScreen ? desktopRoot.widgetScreen.name : "", imageKey: S.Widgets.scene.imageKey, layout: S.Widgets.layoutMode, enabled: S.Widgets.document.enabled, mediaAvailable: S.WidgetMedia.available, musicPlaying: S.Media.playing, spectrumActive: S.Spectrum.active, onBattery: S.Battery.onBattery, progressActive: S.WidgetMedia.progressActive, saving: S.Widgets.saving, visible: widgetSurface.visible, idle: widgetSurface.idle, fullscreen: widgetSurface.occluded, moving: widgetSurface.moving, geometry: widgetSurface.geometry, error: S.Widgets.error}); }
    }
    IpcHandler { target: "settings"; function toggle(): void { desktopRoot.toggle("settings", null); } }
    IpcHandler { target: "clipboard"; function toggle(): void { desktopRoot.toggle("clipboard", null); } }
    // Optional external companion: an explicit environment configuration opts in.
    LazyLoader {
        id: thursdayLoader
        active: !desktopRoot.preview
        component: ThursdayNative.Thursday {
            id: thursday
            repoRoot: Quickshell.env("SUMI_THURSDAY_ROOT") || ""
            theme: Theme
            // The integration also receives its backend's local preference.
            // Re-apply the desktop preference without editing external code.
            onReducedMotionChanged: if (reducedMotion !== Theme.effectiveReducedMotion) Qt.callLater(() => { thursday.reducedMotion = Theme.effectiveReducedMotion; })
            Connections { target: Theme; function onEffectiveReducedMotionChanged() { thursday.reducedMotion = Theme.effectiveReducedMotion; } }
            Component.onCompleted: reducedMotion = Theme.effectiveReducedMotion
        }
    }
    // No external checkout is imported into the public shell.
    Variants { model: Quickshell.screens; Bar { app: desktopRoot } }
    Variants { id: overlays; model: Quickshell.screens; Overlay { app: desktopRoot } }
    DesktopWidgets { id: widgetSurface; modelData: desktopRoot.widgetScreen; app: desktopRoot }
}
