pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import "integrations/SpeechLevels.js" as SpeechLevels
import "config"
import "services" as S
import "components" as C

PanelWindow {
    id: root
    required property var modelData
    required property var app
    property real centerRoom: 420
    screen: modelData
    anchors { top: true }
    margins.top: notch ? 0 : 4
    implicitWidth: Math.min(664, Math.max(1, modelData ? modelData.width - 24 : 664))
    implicitHeight: Math.min(660, Math.max(1, modelData ? modelData.height - 64 : 660))
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "sumi-island"
    WlrLayershell.layer: fullscreen ? WlrLayer.Overlay : WlrLayer.Top
    WlrLayershell.keyboardFocus: pinned ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None

    readonly property bool notch: Settings.islandNotch
    readonly property real expandedWidth: Math.min(pinned ? content.preferredWidth : notificationHere ? 500 : assistantOutputHere ? 560 : 420, Math.max(1, width - 24))
    readonly property int clockPixelSize: centerRoom < 160 ? 20 : 26
    readonly property int periodPixelSize: centerRoom < 160 ? 9 : 10
    property var monitor: Hyprland.monitors.values.find(candidate => candidate && modelData && candidate.name === modelData.name) || null
    readonly property bool fullscreen: !!(monitor && monitor.activeWorkspace && monitor.activeWorkspace.hasFullscreen)
    property bool idle: idleMonitor.isIdle
    readonly property bool canOpen: !!modelData && !idle && !app.nativeDialogOpen && app.panel === ""
    readonly property bool eligible: !!modelData && (app.barVisible || pinned) && (!fullscreen || pinned || criticalHere)
    property string section: "home"
    readonly property bool availableForInteraction: eligible && !idle && !app.nativeDialogOpen && app.panel === ""
    readonly property bool expanded: peek || pinned || automaticPreview || assistantOutputHere
    property bool peek: false
    property bool pinned: false
    property bool hovered: false
    property bool suppressed: false
    property bool initialized: false
    property bool settling: false
    property string lastApplication: Hyprland.activeToplevel ? Hyprland.activeToplevel.address : ""
    property string returnApplication: ""
    property int returnWorkspace: 0
    property double now: Date.now()
    property real mediaPosition: 0
    property int spectrumConsumer: 0
    readonly property bool targetedEvent: S.IslandEvents.active && S.IslandEvents.eventScreenName === (modelData ? modelData.name : "")
    readonly property bool criticalHere: targetedEvent && S.IslandEvents.eventCritical && !idle && !app.nativeDialogOpen && app.panel === ""
    readonly property bool eventHere: targetedEvent && !idle && (!fullscreen || S.IslandEvents.eventCritical)
    readonly property var notificationHere: eventHere ? S.IslandEvents.notification : null
    readonly property bool automaticPreview: availableForInteraction && !pinned && (!!notificationHere || (eventHere && S.IslandEvents.eventPriority >= 80))
    readonly property var assistant: typeof app.thursdayBackend === "undefined" ? null : app.thursdayBackend
    readonly property bool assistantOutputHere: typeof app.thursdayOutputActive !== "undefined" && app.thursdayOutputActive
        && (app.thursdayOutputScreen === (modelData ? modelData.name : "") || (!app.thursdayOutputScreen && modelData === app.notificationScreen))
        && availableForInteraction && !fullscreen && !pinned && !automaticPreview
    readonly property var speechSamples: effectsActive && !!assistant && assistant.speaking
        ? SpeechLevels.reading(assistant.audioEnvelope, assistant.playbackPosition, true, 20).bars.map(value => Math.min(100, Math.sqrt(value) * 240)) : []
    readonly property bool assistantActive: !!assistant && (assistant.voiceActive || assistant.sendPending || assistant.busy || assistant.taskActive || assistant.speaking || assistant.confirmations.length > 0)
    readonly property string activity: eventHere ? "event" : assistantActive || assistantOutputHere ? "thursday" : S.Recording.recording ? "recording" : app.focusRunning ? "focus" : S.IslandMedia.playing ? "media" : "idle"
    readonly property real minimumClockWidth: clockMetric.width + 2 * (periodMetric.width + 18)
    readonly property real compactWidth: Math.min(expandedWidth, Math.max(minimumClockWidth, Math.min(centerRoom, activity === "idle" ? 176 : 320)))
    property real bodyWidth: expanded ? expandedWidth : compactWidth
    property real bodyHeight: pinned ? Math.min(height, content.preferredHeight) : automaticPreview ? Math.min(height, notificationHere ? 236 : 174) : assistantOutputHere ? Math.min(height, content.assistantPreferredHeight) : peek ? Math.min(height, notch ? 222 : 216) : notch ? 40 : 36
    readonly property bool effectsActive: availableForInteraction
    readonly property bool spectrumDemand: effectsActive && activity === "media" && !pinned && content.hasFlanks
    readonly property bool progressDemand: effectsActive && ((pinned && section === "media") || (peek && !automaticPreview)) && !!S.IslandMedia.player && S.IslandMedia.player.positionSupported && S.IslandMedia.playing
    readonly property real inputX: (width - bodyWidth) / 2
    readonly property real inputWidth: availableForInteraction ? bodyWidth : 0
    readonly property real inputHeight: availableForInteraction ? bodyHeight : 0
    readonly property alias visual: content
    visible: eligible && !app.nativeDialogOpen && app.panel === ""

    TextMetrics { id: clockMetric; font.family: Theme.fontMono; font.pixelSize: root.clockPixelSize; font.weight: Font.DemiBold; text: S.Clock.time }
    TextMetrics { id: periodMetric; font.family: Theme.font; font.pixelSize: root.periodPixelSize; font.weight: Font.Bold; text: S.Clock.period }
    IdleMonitor { id: idleMonitor; objectName: "islandIdle"; enabled: root.eligible; timeout: 60; respectInhibitors: false }
    Behavior on bodyWidth { enabled: !root.settling; NumberAnimation { duration: Theme.effectiveReducedMotion ? 0 : Theme.batteryMotion ? 120 : 260; easing.type: Easing.OutQuint } }
    Behavior on bodyHeight { enabled: !root.settling; NumberAnimation { duration: Theme.effectiveReducedMotion ? 0 : Theme.batteryMotion ? 120 : 280; easing.type: Easing.OutQuint } }

    // Only the black shape takes pointer input. The rest of this bounded native
    // window is transparent and passes through to applications below it.
    mask: Region {
        Region {
            x: content.surface.x; y: content.surface.y
            width: root.availableForInteraction ? content.surface.width : 0
            height: root.availableForInteraction ? content.surface.height : 0
            radius: content.surface.radius
            topLeftRadius: content.surface.topLeftRadius
            topRightRadius: content.surface.topRightRadius
        }
        Region {
            x: content.headerSurface.x; y: content.headerSurface.y
            width: root.availableForInteraction ? content.headerSurface.width : 0
            height: root.availableForInteraction ? content.headerSurface.height : 0
            radius: content.headerSurface.radius
            topLeftRadius: content.headerSurface.topLeftRadius
            topRightRadius: content.headerSurface.topRightRadius
        }
        // Concave bezel shoulders are decoration and take no pointer input.
    }

    function enterHover() {
        hovered = true;
        leaveDelay.stop();
        if (availableForInteraction && !suppressed && !pinned) hoverDelay.restart();
    }
    function leaveHover() {
        hovered = false;
        suppressed = false;
        hoverDelay.stop();
        if (!pinned) leaveDelay.restart();
    }
    function pin(requestedSection = "controls") {
        if (!canOpen) return;
        section = ["home", "inbox", "media", "controls", "thursday"].indexOf(requestedSection) >= 0 ? requestedSection : "home";
        if (typeof app.dismissIslands === "function") app.dismissIslands(root);
        returnApplication = Hyprland.activeToplevel ? Hyprland.activeToplevel.address : lastApplication;
        returnWorkspace = monitor && monitor.activeWorkspace ? monitor.activeWorkspace.id || 0 : 0;
        hoverDelay.stop(); leaveDelay.stop();
        suppressed = false;
        pinned = true; peek = false;
        refreshPosition();
        // The layer is already mapped. Acquire only after the explicit click,
        // never while merely hovering or when a panel is taking over focus.
        Qt.callLater(() => {
            if (!root.pinned || !root.availableForInteraction) return;
            focusGrab.active = true;
            content.focusDefault();
        });
    }
    function togglePin() { if (pinned) dismiss(true); else pin(eventHere ? S.IslandEvents.eventSection : assistantActive || assistantOutputHere ? "thursday" : "controls"); }
    function dismiss(restoreApplication) {
        if (!initialized) return;
        const address = restoreApplication && pinned ? returnApplication : "";
        const sameWorkspace = !returnWorkspace || !!(monitor && monitor.activeWorkspace && monitor.activeWorkspace.id === returnWorkspace);
        returnApplication = "";
        hoverDelay.stop(); leaveDelay.stop();
        focusGrab.active = false;
        pinned = false; peek = false;
        suppressed = hovered;
        if (!eligible || idle) {
            settling = true;
            bodyWidth = Qt.binding(() => root.expanded ? root.expandedWidth : root.compactWidth);
            bodyHeight = Qt.binding(() => root.pinned ? Math.min(root.height, content.preferredHeight) : root.automaticPreview ? Math.min(root.height, root.notificationHere ? 236 : 174) : root.assistantOutputHere ? Math.min(root.height, content.assistantPreferredHeight) : root.peek ? Math.min(root.height, root.notch ? 222 : 216) : root.notch ? 40 : 36);
            settling = false;
        }
        if (address && sameWorkspace && Hyprland.toplevels.values.some(window => window && window.address === address))
            Qt.callLater(() => S.HyprlandActions.focusWindow(address));
    }
    function refreshPosition() {
        const player = S.IslandMedia.player;
        mediaPosition = player && player.positionSupported ? Math.max(0, player.position) : 0;
        now = Date.now();
    }
    function openPanel(name) { dismiss(); app.open(name, modelData); }
    function selectSection(name) {
        if (pinned) section = name;
        else pin(name);
    }
    function openSettings(name) { dismiss(); app.openSettings(name, modelData); }
    function selectCapture(annotate, record) {
        dismiss();
        if (typeof app.selectCapture === "function") app.selectCapture(annotate, record);
    }
    onFullscreenChanged: if (initialized) dismiss()
    onSectionChanged: if (pinned) refreshPosition()
    onAvailableForInteractionChanged: if (!availableForInteraction) dismiss()
    onNotchChanged: dismiss()
    onWidthChanged: dismiss()
    onProgressDemandChanged: if (progressDemand) refreshPosition()
    onSpectrumDemandChanged: S.Spectrum.setDemand(spectrumConsumer, spectrumDemand)
    Component.onCompleted: {
        initialized = true;
        spectrumConsumer = S.Spectrum.createConsumer();
        S.Spectrum.setDemand(spectrumConsumer, spectrumDemand);
        if (typeof app.registerIsland === "function") app.registerIsland(root);
        refreshPosition();
    }
    Component.onDestruction: {
        focusGrab.active = false;
        S.Spectrum.setDemand(spectrumConsumer, false);
        if (typeof app.unregisterIsland === "function") app.unregisterIsland(root);
    }
    Connections {
        target: root.app
        function onBarVisibleChanged() { if (!root.app.barVisible) root.dismiss(); }
        function onPanelChanged() { if (root.app.panel !== "") root.dismiss(); }
        function onNativeDialogOpenChanged() { if (root.app.nativeDialogOpen) root.dismiss(); }
        function onFocusRunningChanged() { root.now = Date.now(); }
    }
    Connections {
        target: Hyprland
        function onActiveToplevelChanged() { if (Hyprland.activeToplevel) root.lastApplication = Hyprland.activeToplevel.address; }
    }
    Connections { target: S.IslandMedia; function onPlayerChanged() { root.refreshPosition(); } }
    Connections {
        target: S.IslandMedia.player
        ignoreUnknownSignals: true
        function onPositionChanged() { if (root.progressDemand) root.refreshPosition(); }
        function onTrackChanged() { root.refreshPosition(); }
    }
    Timer { id: hoverDelay; interval: 150; onTriggered: { if (root.hovered && root.availableForInteraction && !root.suppressed) { root.peek = true; root.refreshPosition(); } } }
    Timer { id: leaveDelay; interval: 250; onTriggered: if (!root.hovered && !root.pinned) root.peek = false }
    Timer { interval: S.Battery.onBattery || S.Battery.profile === "power-saver" ? 5000 : 1000; repeat: true; running: root.progressDemand; onTriggered: root.refreshPosition() }
    Timer { interval: 1000; repeat: true; running: root.effectsActive && root.app.focusRunning; onTriggered: root.now = Date.now() }
    HyprlandFocusGrab {
        id: focusGrab
        objectName: "islandFocusGrab"
        windows: [root]
        onCleared: root.dismiss()
    }
    C.IslandContent {
        id: content
        anchors.fill: parent
        app: root.app
        screenInfo: root.modelData
        notch: root.notch
        open: root.expanded
        pinned: root.pinned
        interactive: root.availableForInteraction
        effectsActive: root.effectsActive
        bodyWidth: root.bodyWidth
        bodyHeight: root.bodyHeight
        headerRoom: Math.max(root.minimumClockWidth, Math.min(root.centerRoom, 420))
        clockPixelSize: root.clockPixelSize
        periodPixelSize: root.periodPixelSize
        section: root.section
        notification: root.notificationHere
        alertPreview: root.automaticPreview
        criticalAttention: S.IslandEvents.criticalAttention
        unread: S.Notifications.unread
        activity: root.activity
        assistantAutoOutput: root.assistantOutputHere
        assistantSpeaking: !!root.assistant && root.assistant.speaking
        assistantSamples: root.speechSamples
        assistantLabel: root.assistant ? root.assistant.sendPending ? "Sending" : root.assistant.statusText : ""
        assistantText: root.assistant ? (root.assistantOutputHere ? root.assistant.latestAnswer : root.assistant.transcript || root.assistant.latestAnswer || "") : ""
        eventSection: root.eventHere ? S.IslandEvents.eventSection : "home"
        eventKind: root.eventHere ? S.IslandEvents.eventKind : ""
        eventLabel: root.eventHere ? S.IslandEvents.eventLabel : ""
        eventValue: root.eventHere ? S.IslandEvents.eventValue : 0
        now: root.now
        mediaPosition: root.mediaPosition
        onSectionRequested: section => root.selectSection(section)
        onOpenPanelRequested: name => root.openPanel(name)
        onSettingsRequested: name => root.openSettings(name)
        onCaptureRequested: annotate => root.selectCapture(annotate, false)
        onRecordingRequested: root.selectCapture(false, true)
        onEventDismissRequested: S.IslandEvents.dismissCurrent()
        onThursdayFullChatRequested: { root.dismiss(); if (typeof root.app.openThursdayFull === "function") root.app.openThursdayFull(); }
        onHeaderClicked: root.togglePin()
        onDismissRequested: root.dismiss(true)
        onHoverChanged: hovered => { if (hovered) root.enterHover(); else root.leaveHover(); }
        onCalendarRequested: root.openPanel("calendar")
        onMediaRequested: root.openPanel("media")
        onFocusRequested: root.openPanel("pomodoro")
    }
}
