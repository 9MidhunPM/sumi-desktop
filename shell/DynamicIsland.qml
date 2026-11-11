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
    implicitWidth: Math.min(704, Math.max(1, modelData ? modelData.width - 8 : 704))
    implicitHeight: Math.min(660, Math.max(1, modelData ? modelData.height - 48 : 660))
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "sumi-island"
    WlrLayershell.layer: fullscreen ? WlrLayer.Overlay : WlrLayer.Top
    WlrLayershell.keyboardFocus: pinned ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None

    readonly property bool notch: Settings.islandNotch
    readonly property real expandedWidth: Math.min(pinned && !previewPinned ? content.preferredWidth : notificationHere ? content.notificationPreferredWidth : assistantOutputHere ? 520 : 420, Math.max(1, width - 24))
    readonly property int clockPixelSize: 26
    readonly property int periodPixelSize: 10
    property var monitor: Hyprland.monitors.values.find(candidate => candidate && modelData && candidate.name === modelData.name) || null
    readonly property bool fullscreen: !!(monitor && monitor.activeWorkspace && monitor.activeWorkspace.hasFullscreen)
    property bool idle: idleMonitor.isIdle
    readonly property bool selectingCapture: typeof app.captureSelecting !== "undefined" && app.captureSelecting
    readonly property bool canOpen: !!modelData && !idle && !app.nativeDialogOpen && app.panel === ""
    readonly property bool eligible: !!modelData && (app.barVisible || pinned) && (!fullscreen || pinned || criticalHere || selectingCapture)
    property string section: typeof app.islandSession !== "undefined" ? app.islandSession.route : "home"
    readonly property bool launcherReady: content.launcherReady
    function prepare(route, fresh) { content.prepare(route, fresh); }
    readonly property bool availableForInteraction: eligible && !idle && !app.nativeDialogOpen && app.panel === ""
    readonly property bool expanded: peek || pinned || automaticPreview || assistantOutputHere
    property bool peek: false
    property bool pinned: false
    property bool previewPinned: false
    property string previewActivity: ""
    property string peekActivity: ""
    property bool hovered: false
    property bool suppressed: false
    property bool previewSuppressed: false
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
    readonly property bool eventHere: targetedEvent && !idle && (!fullscreen || S.IslandEvents.eventCritical) && (!assistantActive || S.IslandEvents.eventPriority >= 80)
    readonly property var notificationHere: eventHere ? S.IslandEvents.notification : null
    readonly property bool automaticPreview: availableForInteraction && !previewSuppressed && !pinned && (!!notificationHere || (eventHere && S.IslandEvents.eventPriority >= 80))
    readonly property var assistant: typeof app.thursdayBackend === "undefined" ? null : app.thursdayBackend
    readonly property bool assistantOutputHere: typeof app.thursdayOutputActive !== "undefined" && app.thursdayOutputActive
        && (app.thursdayOutputScreen === (modelData ? modelData.name : "") || (!app.thursdayOutputScreen && modelData === app.notificationScreen))
        && availableForInteraction && !previewSuppressed && !fullscreen && (!pinned || previewPinned) && !automaticPreview
    readonly property var speechSamples: effectsActive && !!assistant && assistant.speaking
        ? SpeechLevels.reading(assistant.audioEnvelope, assistant.playbackPosition, true, 20).bars.map(value => Math.min(100, Math.sqrt(value) * 240)) : []
    readonly property bool assistantActive: !!assistant && (assistant.voiceActive || assistant.sendPending || assistant.busy || assistant.taskActive || assistant.speaking || assistant.confirmations.length > 0)
    readonly property string activity: selectingCapture ? "capture" : eventHere ? "event" : assistantActive || assistantOutputHere ? "thursday" : S.Recording.recording ? "recording" : app.focusRunning ? "focus" : (S.IslandMedia.playing || ((previewPinned && previewActivity === "media" || peek && peekActivity === "media") && S.IslandMedia.available)) ? "media" : "idle"
    readonly property real minimumClockWidth: clockMetric.width + 36
    readonly property real compactWidth: Math.min(expandedWidth, Math.max(minimumClockWidth, Math.min(centerRoom, activity === "idle" ? 176 : activity === "media" ? 220 : 320)))
    property real openingWidth: 176
    property real openingHeight: 36
    property real bodyWidth: pinned && !previewPinned && !content.dashboardReady ? openingWidth : expanded ? expandedWidth : compactWidth
    property real bodyHeight: pinned && !previewPinned && !content.dashboardReady ? openingHeight : pinned && !previewPinned ? Math.min(height, content.preferredHeight) : automaticPreview ? Math.min(height, notificationHere ? content.notificationPreferredHeight : 174) : assistantOutputHere ? Math.min(height, assistant && assistant.latestAnswer ? 236 : 208) : (peek || previewPinned) ? Math.min(height, activity === "media" ? (notch ? 206 : 202) : (notch ? 222 : 216)) : activity === "media" ? 50 : notch ? 46 : 42
    readonly property bool effectsActive: availableForInteraction
    readonly property bool spectrumDemand: effectsActive && S.IslandMedia.playing && ((activity === "media" && (!pinned || previewPinned) && content.hasVisibleMediaWave) || (pinned && !previewPinned && content.dashboardReady && (section === "media" || section === "controls" || section === "home" || content.headerWidth >= 420)))
    readonly property bool progressDemand: effectsActive && ((pinned && (previewPinned || section === "media")) || (peek && !automaticPreview)) && !!S.IslandMedia.player && S.IslandMedia.player.positionSupported && S.IslandMedia.playing
    readonly property bool morphing: widthMorph.running || heightMorph.running
    readonly property real inputX: (width - bodyWidth) / 2
    readonly property real inputWidth: availableForInteraction ? bodyWidth : 0
    readonly property real inputHeight: availableForInteraction ? bodyHeight : 0
    readonly property alias visual: content
    visible: eligible && (!app.nativeDialogOpen || selectingCapture || pinned) && app.panel === ""

    TextMetrics { id: clockMetric; font.family: Theme.fontMono; font.pixelSize: root.clockPixelSize; font.weight: Font.DemiBold; text: S.Clock.time }
    TextMetrics { id: periodMetric; font.family: Theme.font; font.pixelSize: root.periodPixelSize; font.weight: Font.Bold; text: S.Clock.period }
    IdleMonitor { id: idleMonitor; objectName: "islandIdle"; enabled: root.eligible; timeout: 60; respectInhibitors: false }
    Behavior on bodyWidth { enabled: !root.settling; NumberAnimation { id: widthMorph; duration: root.activity === "media" && (!root.pinned || root.previewPinned) ? IslandStyle.musicTransition : IslandStyle.geometryTransition; easing.type: Easing.OutCubic } }
    Behavior on bodyHeight { enabled: !root.settling; NumberAnimation { id: heightMorph; duration: root.activity === "media" && (!root.pinned || root.previewPinned) ? IslandStyle.musicTransition : IslandStyle.geometryTransition; easing.type: Easing.OutCubic } }

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
    function pin(requestedSection = "", preview = false) {
        if (!canOpen) return;
        openingWidth = bodyWidth; openingHeight = bodyHeight;
        if (requestedSection) selectRoute(requestedSection);
        if (typeof app.dismissIslands === "function") app.dismissIslands(root);
        returnApplication = Hyprland.activeToplevel ? Hyprland.activeToplevel.address : lastApplication;
        returnWorkspace = monitor && monitor.activeWorkspace ? monitor.activeWorkspace.id || 0 : 0;
        hoverDelay.stop(); leaveDelay.stop();
        suppressed = false;
        previewSuppressed = false;
        previewActivity = preview ? activity : ""; previewPinned = preview; pinned = true; peek = false;
        refreshPosition();
        // The layer is already mapped. Acquire only after the explicit click,
        // never while merely hovering or when a panel is taking over focus.
        Qt.callLater(() => {
            if (!root.pinned || !root.availableForInteraction) return;
            focusGrab.active = true;
            content.focusDefault();
        });
    }
    function togglePin() { if (pinned) dismiss(true); else pin("controls"); }
    function promoteDashboard() { previewPinned = false; content.prepare(section, false); Qt.callLater(() => content.focusDefault()); }
    function dismiss(restoreApplication) {
        if (!initialized) return;
        if (restoreApplication === true) previewSuppressed = true;
        const address = restoreApplication && pinned ? returnApplication : "";
        const sameWorkspace = !returnWorkspace || !!(monitor && monitor.activeWorkspace && monitor.activeWorkspace.id === returnWorkspace);
        returnApplication = "";
        hoverDelay.stop(); leaveDelay.stop();
        focusGrab.active = false;
        pinned = false; previewPinned = false; peek = false;
        suppressed = hovered;
        if (!eligible || idle || app.nativeDialogOpen) {
            settling = true;
            bodyWidth = Qt.binding(() => root.pinned && !root.previewPinned && !content.dashboardReady ? root.openingWidth : root.expanded ? root.expandedWidth : root.compactWidth);
            bodyHeight = Qt.binding(() => root.pinned && !root.previewPinned && !content.dashboardReady ? root.openingHeight : root.pinned && !root.previewPinned ? Math.min(root.height, content.preferredHeight) : root.automaticPreview ? Math.min(root.height, root.notificationHere ? content.notificationPreferredHeight : 174) : root.assistantOutputHere ? Math.min(root.height, root.assistant && root.assistant.latestAnswer ? 236 : 208) : (root.peek || root.previewPinned) ? Math.min(root.height, root.activity === "media" ? (root.notch ? 206 : 202) : (root.notch ? 222 : 216)) : root.activity === "media" ? 50 : root.notch ? 46 : 42);
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
    function openPanel(name) { app.open(name, modelData); }
    function selectSection(name) {
        if (pinned) { selectRoute(name); if (previewPinned) promoteDashboard(); }
        else pin(name);
    }
    function selectRoute(name) {
        if (typeof app.islandSession !== "undefined") app.islandSession.navigate(name, name === "notification" ? app.islandSession.entityId : "");
        else section = name;
    }
    function openSettings(name) { app.openSettings(name, modelData); }
    function selectCapture(annotate, record) {
        if (typeof app.selectCapture === "function") app.selectCapture(annotate, record);
    }
    onFullscreenChanged: if (initialized && !app.nativeDialogOpen) dismiss()
    onSectionChanged: if (pinned) refreshPosition()
    onAvailableForInteractionChanged: if (!availableForInteraction && !app.nativeDialogOpen) Qt.callLater(() => { if (!root.availableForInteraction && !root.app.nativeDialogOpen) root.dismiss(); })
    onNotchChanged: if (!pinned) dismiss()
    onWidthChanged: if (!app.nativeDialogOpen) dismiss()
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
        function onBarVisibleChanged() { if (!root.app.barVisible && !root.app.nativeDialogOpen) root.dismiss(); }
        function onPanelChanged() { if (root.app.panel !== "") root.dismiss(); }
        function onNativeDialogOpenChanged() {
            if (root.app.nativeDialogOpen) focusGrab.active = false;
            else if (root.pinned) Qt.callLater(() => { if (root.pinned && root.availableForInteraction && !root.app.nativeDialogOpen) { focusGrab.active = true; content.focusDefault(); } });
        }
        function onFocusRunningChanged() { root.now = Date.now(); }
    }
    Connections {
        target: Hyprland
        function onActiveToplevelChanged() { if (Hyprland.activeToplevel) root.lastApplication = Hyprland.activeToplevel.address; }
    }
    Connections { target: S.IslandEvents; ignoreUnknownSignals: true; function onCurrentChanged() { if (!root.assistantActive) root.previewSuppressed = false; } }
    Connections { target: root.assistant; ignoreUnknownSignals: true; function onVoiceSessionChanged() { root.previewSuppressed = false; } }
    Connections { target: S.IslandMedia; function onPlayerChanged() { root.refreshPosition(); } }
    Connections {
        target: S.IslandMedia.player
        ignoreUnknownSignals: true
        function onPositionChanged() { if (root.progressDemand) root.refreshPosition(); }
        function onTrackChanged() { root.refreshPosition(); }
    }
    Timer { id: hoverDelay; interval: root.activity === "media" ? 60 : 120; onTriggered: { if (root.hovered && root.availableForInteraction && !root.suppressed) { root.peekActivity = root.activity; root.peek = true; root.refreshPosition(); } } }
    Timer { id: leaveDelay; interval: root.activity === "media" ? 180 : 300; onTriggered: if (!root.hovered && !root.pinned) root.peek = false }
    Timer { interval: S.Battery.onBattery || S.Battery.profile === "power-saver" ? 5000 : 1000; repeat: true; running: root.progressDemand; onTriggered: root.refreshPosition() }
    Timer { interval: 1000; repeat: true; running: root.effectsActive && root.app.focusRunning; onTriggered: root.now = Date.now() }
    HyprlandFocusGrab {
        id: focusGrab
        objectName: "islandFocusGrab"
        windows: [root]
        onCleared: if (!root.app.nativeDialogOpen) root.dismiss()
    }
    C.IslandContent {
        id: content
        anchors.fill: parent
        opacity: root.app.nativeDialogOpen ? 0 : 1
        app: root.app
        screenInfo: root.modelData
        notch: root.notch
        open: root.expanded
        pinned: root.pinned && !root.previewPinned
        previewPinned: root.previewPinned
        interactive: root.availableForInteraction
        effectsActive: root.effectsActive
        maximumWidth: Math.max(1, root.width - 24)
        maximumHeight: root.height
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
        assistantRecording: !!root.assistant && root.assistant.recording === true
        assistantSamples: root.speechSamples
        assistantLevel: root.assistant && typeof root.assistant.visualizerLevel === "number" ? root.assistant.visualizerLevel : 0
        assistantProcessing: root.assistantActive && !!root.assistant && !root.assistant.speaking && !root.assistant.recording
        assistantLabel: root.assistant ? root.assistant.sendPending ? "Sending" : ((root.assistant.busy || root.assistant.taskActive) && root.assistant.activity) || root.assistant.statusText : ""
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
        onThursdayFullChatRequested: root.selectSection("thursday")
        onHeaderClicked: root.togglePin()
        onDismissRequested: root.dismiss(true)
        onHoverChanged: hovered => { if (hovered) root.enterHover(); else root.leaveHover(); }
        onCalendarRequested: root.selectSection("calendar")
        onMediaRequested: root.selectSection("media")
        onFocusRequested: root.selectSection("pomodoro")
    }
}
