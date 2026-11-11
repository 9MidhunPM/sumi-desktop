pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import Quickshell.Widgets
import "../config"
import "../services" as S
import "../integrations" as Native

// Pure visual content. The native host owns geometry, focus and demand gates.
FocusScope {
    id: root
    focus: pinned
    required property var app
    property var screenInfo: null
    property bool notch: false
    property bool open: false
    property bool pinned: false
    property bool previewPinned: false
    readonly property bool musicExpanded: open && !pinned && activity === "media" && !hasEvent && !assistantAutoOutput
    readonly property var assistantBackend: typeof app.thursdayBackend === "undefined" ? null : app.thursdayBackend
    property bool interactive: true
    property bool effectsActive: true
    property real bodyWidth: 176
    property real bodyHeight: 32
    property real maximumWidth: 680
    property real maximumHeight: 660
    property bool dashboardReady: false
    property int layoutStableFrames: 0
    property real lastLayoutHeight: -1
    property real lastLayoutWidth: -1
    property int layoutFrames: 0
    property bool revealPending: false
    property real headerRoom: 420
    property string activity: "idle"
    property string section: "home"
    property var notification: null
    property bool alertPreview: false
    property bool criticalAttention: false
    property int unread: 0
    property string eventSection: "home"
    property bool assistantAutoOutput: false
    property bool assistantSpeaking: false
    property bool assistantRecording: false
    property real assistantLevel: 0
    property bool assistantProcessing: false
    property var assistantSamples: []
    TextMetrics { id: notificationSummaryMetric; font.pixelSize: 13; font.weight: Font.DemiBold; text: root.notification ? root.notification.summary || "" : "" }
    TextMetrics { id: notificationBodyMetric; font.pixelSize: 12; text: root.notification ? root.notification.body || "" : "" }
    readonly property real notificationPreferredWidth: Math.min(maximumWidth, Math.max(360, Math.min(500, Math.max(notificationSummaryMetric.width, notificationBodyMetric.width) + 64)))
    readonly property real notificationPreferredHeight: Math.min(340, Math.max(130, notificationPreview.implicitHeight + headerHeight + 20))
    readonly property real assistantPreferredHeight: assistantOutput.implicitHeight + headerHeight + 20
    property string assistantLabel: ""
    readonly property string assistantActiveLabel: assistantRecording ? "Listening" : assistantSpeaking ? "Speaking" : assistantProcessing ? "Thinking" : ""
    property string assistantText: ""
    property string eventKind: ""
    property string eventLabel: ""
    property real eventValue: 0
    property string timeText: S.Clock.time
    property string periodText: S.Clock.period
    property int clockPixelSize: 26
    property int periodPixelSize: 10
    property real now: Date.now()
    property real mediaPosition: 0
    readonly property real requestedWidth: dashboard.item ? dashboard.item.preferredWidth : 640
    readonly property real requestedHeight: dashboard.item ? dashboard.item.preferredHeight + headerHeight + 26 : 440
    property real preferredWidth: 640
    property real preferredHeight: 440
    readonly property real shapeDistance: Math.abs(bodyWidth - Math.min(preferredWidth, maximumWidth)) + Math.abs(bodyHeight - Math.min(preferredHeight, maximumHeight))
    function queueLayout() {
        if (!pinned) return;
        layoutStableFrames = 0; layoutFrames = 0;
        lastLayoutWidth = -1; lastLayoutHeight = -1;
        prepareLayout.restart();
    }
    function updateReveal() { if (pinned && dashboardReady && shapeDistance < 6) revealPending = false; }
    onRequestedWidthChanged: queueLayout()
    onRequestedHeightChanged: queueLayout()
    onMaximumWidthChanged: queueLayout()
    onMaximumHeightChanged: queueLayout()
    onSectionChanged: { revealPending = true; queueLayout(); }
    onBodyWidthChanged: updateReveal()
    onBodyHeightChanged: updateReveal()
    readonly property bool launcherReady: !!dashboard.item && dashboard.item.launcherReady
    function prepare(route, fresh) { if (dashboard.item) dashboard.item.prepare(route, fresh); }
    function back() { return !!dashboard.item && dashboard.item.back(); }
    property var samples: activity === "thursday" ? assistantSamples : S.Spectrum.samples
    readonly property alias surface: blackBody
    readonly property alias headerSurface: headerBackground
    readonly property alias leftFillet: leftShoulder
    readonly property alias rightFillet: rightShoulder
    readonly property bool focusFace: !S.IslandMedia.available && !!app.focusRunning
    readonly property var firstControl: S.IslandMedia.available ? play : focusToggle
    readonly property real headerInset: notch ? 4 : 0
    readonly property real headerHeight: headerInset + 36
    readonly property real headerWidth: bodyWidth
    readonly property bool wideBody: bodyWidth > headerWidth + 0.1
    // A slight upward bias balances the orb visually beneath the notch.
    readonly property real voiceOrbCenterY: Math.max(0, bodyHeight / 2 - 12)
    readonly property bool hasEvent: eventKind.length > 0
    readonly property bool hasFlanks: headerWidth >= 260 || (activity === "media" && !musicExpanded && headerWidth >= 220)
    readonly property bool hasVisibleMediaWave: !pinned && activity === "media" && !hasEvent && (hasFlanks || musicExpanded) && rightFlank.width >= 14
    readonly property real mediaLength: S.IslandMedia.player && S.IslandMedia.player.lengthSupported ? Math.max(0, S.IslandMedia.player.length) : 0
    readonly property real remaining: app.focusRunning ? Math.max(0, app.focusDeadline - now) : Math.max(0, Number(app.focusRemaining) || 0)
    readonly property real focusProgress: Math.max(0, Math.min(1, 1 - remaining / Math.max(1,
        typeof app.focusDuration === "number" ? app.focusDuration : Number(app.focusRemaining) || remaining)))
    signal sectionRequested(string section)
    signal openPanelRequested(string panel)
    signal settingsRequested(string section)
    signal captureRequested(bool annotate)
    signal recordingRequested()
    signal thursdayFullChatRequested()
    signal eventDismissRequested()
    signal headerClicked()
    signal dismissRequested()
    signal hoverChanged(bool hovered)
    signal calendarRequested()
    signal mediaRequested()
    signal focusRequested()

    function duration(milliseconds) {
        const seconds = Math.max(0, Math.ceil(milliseconds / 1000));
        return Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0");
    }
    function focusDefault() {
        if (pinned && dashboard.item) { dashboard.item.focusDefault(); return; }
        if (previewPinned && musicExpanded && headerPlay.enabled) { headerPlay.forceActiveFocus(Qt.OtherFocusReason); return; }
        if (firstControl && firstControl.enabled) firstControl.forceActiveFocus(Qt.OtherFocusReason);
        else calendar.forceActiveFocus(Qt.OtherFocusReason);
    }
    Shortcut {
        sequence: "Escape"
        context: Qt.WindowShortcut
        enabled: (root.pinned || root.previewPinned) && root.interactive
        onActivated: root.dismissRequested()
    }
    Keys.onEscapePressed: event => { dismissRequested(); event.accepted = true; }

    // Measure at the destination width, never at the animated clipping width.
    Timer {
        id: prepareLayout
        interval: 16; repeat: true
        onTriggered: {
            if (!root.pinned || !dashboard.item) { stop(); return; }
            if (!dashboard.item.measurementReady) return;
            const measured = Math.min(root.requestedHeight, root.maximumHeight);
            const measuredWidth = Math.min(root.requestedWidth, root.maximumWidth);
            root.layoutFrames++;
            root.layoutStableFrames = Math.abs(measured - root.lastLayoutHeight) < .5 && Math.abs(measuredWidth - root.lastLayoutWidth) < .5 ? root.layoutStableFrames + 1 : 0;
            root.lastLayoutHeight = measured; root.lastLayoutWidth = measuredWidth;
            if (root.layoutStableFrames >= 1 || root.layoutFrames >= 10) {
                root.preferredWidth = measuredWidth; root.preferredHeight = measured;
                root.dashboardReady = true; stop(); root.updateReveal();
            }
        }
    }
    onPinnedChanged: {
        if (!pinned) { dashboardReady = false; prepareLayout.stop(); }
        else { revealPending = true; queueLayout(); }
    }
    Rectangle {
        id: blackBody
        objectName: "islandBody"
        x: (root.width - root.bodyWidth) / 2
        y: root.wideBody ? root.headerHeight : 0
        width: root.bodyWidth
        height: Math.max(0, root.bodyHeight - y)
        radius: root.open ? 36 : Math.min(25, root.bodyHeight / 2)
        topLeftRadius: root.notch && !root.wideBody ? 0 : radius
        topRightRadius: root.notch && !root.wideBody ? 0 : radius
        color: "transparent"
    }
    Rectangle {
        id: headerBackground
        x: (root.width - width) / 2
        width: root.headerWidth; height: root.headerHeight
        radius: root.notch ? 23 : Math.min(24, root.bodyHeight / 2)
        topLeftRadius: root.notch ? 0 : radius
        topRightRadius: root.notch ? 0 : radius
        color: "transparent"
    }
    IslandNotchFillet {
        id: leftShoulder
        x: headerBackground.x - width; y: 0
        mirrored: true; visible: root.notch; opacity: 0
    }
    IslandNotchFillet {
        id: rightShoulder
        x: headerBackground.x + headerBackground.width; y: 0
        visible: root.notch; opacity: 0
    }
    IslandSilhouette {
        anchors.fill: parent
        bodyWidth: root.bodyWidth; bodyHeight: root.bodyHeight
        headerWidth: root.headerWidth; headerHeight: root.headerHeight
        notch: root.notch; expanded: root.open; focused: root.pinned
    }
    Item {
        id: bodyLayout
        x: (root.width - width) / 2
        width: root.bodyWidth; height: root.bodyHeight
        clip: true
        HoverHandler { onHoveredChanged: root.hoverChanged(hovered) }

        Item {
            id: header
            objectName: "islandHeader"
            x: (parent.width - width) / 2
            y: root.headerInset
            width: root.headerWidth
            height: 36
            MouseArea {
                anchors.fill: parent
                enabled: root.interactive
                cursorShape: Qt.PointingHandCursor
                onClicked: root.headerClicked()
                Accessible.role: Accessible.Button
                Accessible.name: (root.pinned ? "Close Controls" : "Open Controls") + ", " + root.timeText
            }
            Label {
                id: clock
                objectName: "barClockTime"
                visible: !root.musicExpanded
                anchors.centerIn: parent
                anchors.alignWhenCentered: false
                text: root.timeText
                font.family: Theme.fontMono
                font.pixelSize: root.clockPixelSize
                font.weight: Font.DemiBold
                color: "#ffffff"
            }
            Label {
                id: period
                objectName: "barClockPeriod"
                visible: false
                anchors.left: clock.right
                anchors.leftMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                text: root.periodText
                font.pixelSize: root.periodPixelSize
                font.weight: Font.Bold
                color: "#d4d4d8"
            }
            Item {
                id: leftFlank
                objectName: "islandLeftFlank"
                x: root.activity === "media" && !root.hasEvent && !root.musicExpanded ? 10 : 14; height: 28
                anchors.verticalCenter: parent.verticalCenter
                width: Math.max(0, clock.x - x - (root.activity === "media" && !root.hasEvent && !root.musicExpanded ? 6 : 16))
                visible: !root.pinned && (root.hasFlanks || root.activity === "thursday")
                clip: true
                Icon {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.hasEvent || root.activity === "capture" || root.activity === "recording" || (root.activity === "media" && !root.musicExpanded && smallArt.status !== Image.Ready)
                    name: root.activity === "capture" ? "camera" : root.eventKind === "notification" ? "bell" : root.eventKind === "brightness" ? "settings" : root.activity === "thursday" || root.eventKind === "thursday" ? "sparkles" : root.activity === "recording" || root.eventKind === "recording" ? "record" : root.eventKind === "volume" || root.eventKind === "mute" ? (S.Audio.muted ? "volume-x" : "volume") : root.eventKind === "microphone" ? "volume-x" : root.eventKind === "power" ? (S.Battery.charging ? "battery-charging" : "battery") : (root.eventKind === "low-battery" || root.eventKind === "critical-battery") ? "battery" : root.activity === "focus" || root.eventKind.indexOf("focus") >= 0 ? "calendar" : "music"
                    size: 14
                    color: (root.eventKind === "low-battery" || root.eventKind === "critical-battery" || root.activity === "recording") ? Theme.accentWarn : "#ffffff"
                }
                Label {
                    objectName: "islandHeaderActivityLabel"
                    visible: root.activity !== "media" || root.hasEvent
                    x: root.activity === "thursday" && !root.hasEvent ? 0 : root.activity === "media" && !root.hasEvent ? (root.musicExpanded ? 68 : 38) : root.activity === "focus" && !root.hasEvent ? 0 : 21
                    width: Math.max(0, parent.width - x)
                    height: root.activity === "media" && !root.hasEvent ? 16 : parent.height
                    elide: Text.ElideRight
                    text: root.hasEvent ? root.eventLabel : root.activity === "focus" ? root.duration(root.remaining) : root.activity === "capture" ? "Select region" : root.activity === "recording" ? "Recording" : root.activity === "thursday" ? root.assistantLabel : root.activity === "media" ? S.IslandMedia.title : ""
                    font.pixelSize: root.activity === "media" && !root.hasEvent ? 13 : 10
                    font.weight: root.activity === "media" && !root.hasEvent ? Font.DemiBold : Font.Medium
                    color: "#e4e4e7"
                    verticalAlignment: Text.AlignVCenter
                }
                Label {
                    x: root.musicExpanded ? 68 : 38; y: 16; width: Math.max(0, parent.width - x); height: 12
                    visible: false
                    text: S.IslandMedia.artist; font.pixelSize: 10; color: "#a8a8ae"; elide: Text.ElideRight
                }
            }
            Item {
                id: rightFlank
                objectName: "islandRightFlank"
                x: root.activity === "media" && !root.hasEvent ? (root.musicExpanded ? Math.max(clock.x + clock.width + 8, parent.width - 60) : clock.x + clock.width + 6) : clock.x + clock.width + 16
                width: Math.max(0, parent.width - x - (root.activity === "media" && !root.hasEvent && !root.musicExpanded ? 10 : 14))
                height: root.activity === "thursday" && !root.hasEvent && !root.open ? 28 : 14
                y: root.musicExpanded ? 48 : (parent.height - height) / 2
                Behavior on y { NumberAnimation { duration: root.activity === "media" ? IslandStyle.musicTransition : IslandStyle.geometryTransition; easing.type: Easing.OutCubic } }
                clip: true
                visible: !root.pinned && (root.hasFlanks || root.musicExpanded || root.activity === "thursday")
                Native.SpeechOrb {
                    objectName: "islandThursdayCompactOrb"
                    width: 28; height: 28
                    anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                    visible: root.activity === "thursday" && !root.hasEvent && !root.open && !root.assistantAutoOutput
                    active: visible && root.effectsActive && (root.assistantSpeaking || root.assistantRecording || root.assistantProcessing)
                    effectsActive: root.effectsActive && !root.assistantAutoOutput && !(root.pinned && root.section === "thursday")
                    level: root.assistantLevel
                    processing: root.assistantProcessing
                    reducedMotion: Theme.effectiveReducedMotion
                }
                IslandWaveform {
                    objectName: "islandThursdayHeaderMeter"
                    anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(40, parent.width); height: 14; barCount: 7
                    visible: false
                    tint: "#a6c9ed"; active: root.effectsActive && (root.assistantRecording || root.assistantSpeaking)
                    samples: [root.assistantLevel * 45, root.assistantLevel * 70, root.assistantLevel * 90, root.assistantLevel * 100, root.assistantLevel * 90, root.assistantLevel * 70, root.assistantLevel * 45]
                }
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width; height: 3; radius: 1.5
                    color: "#333338"
                    visible: (root.hasEvent && root.eventKind !== "notification") || root.activity === "focus"
                    Rectangle {
                        width: parent.width * (root.hasEvent ? Math.max(0, Math.min(1, root.eventValue)) : root.focusProgress)
                        height: parent.height; radius: 1.5
                        color: (root.eventKind === "low-battery" || root.eventKind === "critical-battery" || root.activity === "recording") ? Theme.accentWarn : "#ffffff"
                    }
                }
                Label { anchors.fill: parent; visible: root.activity === "capture"; text: "Esc to cancel"; color: "#c4c5ce"; font.pixelSize: 9; verticalAlignment: Text.AlignVCenter }
                Row {
                    id: musicWave
                    objectName: "islandCompactWave"
                    width: root.musicExpanded ? parent.width : Math.min(42, parent.width)
                    height: parent.height
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 1
                    visible: !root.hasEvent && root.activity === "media"
                    Repeater {
                        model: 20
                        Rectangle {
                            required property int index
                            objectName: "islandWave" + index
                            width: Math.max(0, (musicWave.width - 19) / 20)
                            height: Math.max(2, Math.min(100, Math.max(0, Number(root.samples[index]) || 0)) * 0.14)
                            y: (rightFlank.height - height) / 2
                            radius: 1
                            color: "#e7a88f"
                            Behavior on height { NumberAnimation { duration: Motion.control; easing.type: Easing.OutCubic } }
                        }
                    }
                }
            }
            Row {
                id: dashboardLeftLane
                objectName: "islandDashboardLeftLane"
                x: 12; height: 36; anchors.verticalCenter: parent.verticalCenter
                width: Math.max(0, clock.x - x - 10); clip: true; spacing: 4
                visible: root.pinned && root.dashboardReady
                ActionButton {
                    objectName: "islandHeaderSearchBack"
                    width: Math.min(parent.width, root.section === "controls" || root.section === "home" ? 92 : 70); height: 36
                    quiet: true; textColor: "white"; font.pixelSize: 12
                    iconName: root.section === "controls" || root.section === "home" ? "search" : ""; iconSize: 16
                    text: root.section === "controls" || root.section === "home" ? "Search" : "‹  Back"
                    tooltip: root.section === "controls" || root.section === "home" ? "Search apps, files and actions" : "Back to previous page"
                    onClicked: { if (root.section === "controls" || root.section === "home") root.sectionRequested("launcher"); else if (!root.back()) root.sectionRequested("controls"); }
                }
                Label { height: 36; width: Math.max(0, parent.width - 75); visible: (root.activity === "thursday" && root.assistantActiveLabel.length > 0) || (root.section !== "controls" && root.section !== "home"); text: root.activity === "thursday" ? root.assistantActiveLabel : root.section === "media" ? "Now playing" : root.section === "thursday" ? "Thursday" : root.section.charAt(0).toUpperCase() + root.section.slice(1); elide: Text.ElideRight; color: "#aaaab3"; font.pixelSize: 11 }
            }
            Row {
                id: dashboardRightLane
                objectName: "islandDashboardRightLane"
                anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                height: 36; spacing: 4
                visible: root.pinned && root.dashboardReady
                IslandWaveform { objectName: "islandDashboardHeaderWave"; width: 28; height: 18; anchors.verticalCenter: parent.verticalCenter; barCount: 7; samples: S.Spectrum.samples; active: root.effectsActive && S.IslandMedia.playing; visible: S.IslandMedia.playing && root.section !== "controls" && root.section !== "media" && root.headerWidth >= 420 }
                ActionButton { objectName: "islandHeaderSettings"; width: root.bodyWidth < 420 ? 30 : 36; height: 36; iconName: "settings"; iconSize: 16; quiet: true; textColor: "white"; tooltip: "Island settings"; onClicked: root.sectionRequested("settings") }
                ActionButton { objectName: "islandHeaderClose"; width: root.bodyWidth < 420 ? 30 : 36; height: 36; text: "×"; font.pixelSize: 20; quiet: true; textColor: "white"; tooltip: "Close island"; onClicked: root.dismissRequested() }
            }
        }

        Row {
            objectName: "islandExpandedMusicTransport"
            x: musicPreview.x + Math.max(0, (musicPreview.width - width) / 2)
            y: root.headerInset + 130; spacing: 2; height: 36
            visible: root.musicExpanded
            IslandPreviewButton { objectName: "islandHeaderMusicPrevious"; width: Math.max(20, Math.min(36, (musicPreview.width - 4) / 3)); height: 36; iconName: "chevron-down"; rotation: 90; iconSize: 20; quiet: true; tooltip: "Previous track"; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canGoPrevious; onClicked: S.IslandMedia.previous() }
            IslandPreviewButton { id: headerPlay; objectName: "islandHeaderMusicPlay"; width: Math.max(20, Math.min(36, (musicPreview.width - 4) / 3)); height: 36; iconName: S.IslandMedia.playing ? "pause" : "play"; iconSize: 21; quiet: true; tooltip: S.IslandMedia.playing ? "Pause" : "Play"; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canTogglePlaying; onClicked: S.IslandMedia.toggle() }
            IslandPreviewButton { objectName: "islandHeaderMusicNext"; width: Math.max(20, Math.min(36, (musicPreview.width - 4) / 3)); height: 36; iconName: "chevron-down"; rotation: -90; iconSize: 20; quiet: true; tooltip: "Next track"; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canGoNext; onClicked: S.IslandMedia.next() }
        }
        ClippingRectangle {
            id: animatedAlbum
            objectName: "islandCompactAlbum"
            x: root.musicExpanded ? 20 : leftFlank.x + (leftFlank.width - width) / 2
            y: root.headerInset + (root.musicExpanded ? 28 : 4)
            width: root.musicExpanded ? Math.min(140, Math.max(64, (parent.width - 44) * 0.4)) : 28
            height: width
            radius: root.musicExpanded ? 20 : 8
            color: "#1c1c1f"
            visible: !root.pinned && root.activity === "media" && !root.hasEvent && (root.musicExpanded || (leftFlank.visible && smallArt.status === Image.Ready))
            Behavior on x { NumberAnimation { duration: IslandStyle.musicTransition; easing.type: Easing.OutCubic } }
            Behavior on y { NumberAnimation { duration: IslandStyle.musicTransition; easing.type: Easing.OutCubic } }
            Behavior on width { NumberAnimation { duration: IslandStyle.musicTransition; easing.type: Easing.OutCubic } }
            Behavior on radius { NumberAnimation { duration: IslandStyle.musicTransition; easing.type: Easing.OutCubic } }
            Icon { anchors.centerIn: parent; name: "music"; size: 24; color: "#bdbdc5"; visible: smallArt.status !== Image.Ready }
            ArtworkImage { id: smallArt; anchors.fill: parent; artworkUrl: S.IslandMedia.artUrl; active: root.effectsActive && root.activity === "media" && !root.hasEvent; fillMode: Image.PreserveAspectCrop; sourceSize: Qt.size(280,280); visible: status === Image.Ready }
        }
        Column {
            objectName: "islandMusicMetadata"
            x: musicPreview.x; y: root.headerInset + 38; width: Math.max(0, musicPreview.width - 52); spacing: 3
            visible: root.musicExpanded
            Label { width: parent.width; text: S.IslandMedia.title; font.pixelSize: 13; font.weight: Font.DemiBold; color: "white"; elide: Text.ElideRight }
            Label { width: parent.width; text: S.IslandMedia.artist; font.pixelSize: 10; color: "#a8a8ae"; elide: Text.ElideRight }
        }
        Item {
            id: details
            objectName: "islandDetails"
            x: 16; y: root.headerInset + 46
            width: Math.max(0, parent.width - 32)
            height: 164
            opacity: root.open && !root.pinned && !root.notification && !root.alertPreview && root.activity !== "thursday" && root.activity !== "media" && !root.assistantAutoOutput ? 1 : 0
            visible: opacity > 0.001
            enabled: root.interactive && root.open
            onVisibleChanged: if (visible && root.pinned) Qt.callLater(root.focusDefault)
            Behavior on opacity { NumberAnimation { duration: root.open ? Motion.content : Motion.control; easing.type: Easing.OutCubic } }

            ClippingRectangle {
                id: face
                x: 2; y: 7
                width: 88; height: 88; radius: 18
                color: "#111114"
                visible: S.IslandMedia.available
                Icon { anchors.centerIn: parent; name: "music"; size: 42; color: "#d4d4d8"; visible: largeArt.status !== Image.Ready }
                ArtworkImage {
                    id: largeArt
                    objectName: "islandArtwork"
                    anchors.fill: parent
                    artworkUrl: S.IslandMedia.artUrl
                    active: root.effectsActive && details.visible && S.IslandMedia.available
                    sourceSize: Qt.size(264, 264)
                    fillMode: Image.PreserveAspectCrop
                    visible: status === Image.Ready
                }
            }
            Canvas {
                id: focusRing
                x: 2; y: 7; width: 88; height: 88
                visible: root.focusFace
                onVisibleChanged: requestPaint()
                Connections { target: root; function onFocusProgressChanged() { focusRing.requestPaint(); } }
                onPaint: {
                    const ctx = getContext("2d");
                    ctx.reset(); ctx.lineWidth = 6; ctx.lineCap = "round";
                    ctx.strokeStyle = "#242429";
                    ctx.beginPath(); ctx.arc(44,44,36,0,Math.PI*2); ctx.stroke();
                    ctx.strokeStyle = "#ffffff";
                    ctx.beginPath(); ctx.arc(44,44,36,-Math.PI/2,-Math.PI/2+Math.PI*2*root.focusProgress); ctx.stroke();
                }
                Icon { anchors.centerIn: parent; name: "calendar"; size: 28; color: "#ffffff" }
            }
            Item {
                id: faceWords
                x: 106; y: 7
                width: Math.max(0, glanceTime.x - x - 14); height: 88
                visible: S.IslandMedia.available || root.focusFace
                Label {
                    width: parent.width; height: 34
                    text: root.focusFace ? "Focus session" : S.IslandMedia.title
                    font.pixelSize: 14; font.weight: Font.DemiBold
                    color: "#ffffff"; wrapMode: Text.Wrap; maximumLineCount: 2
                }
                Label {
                    y: 38; width: parent.width; height: 18
                    text: root.focusFace ? root.duration(root.remaining) : S.IslandMedia.artist
                    font.family: root.focusFace ? Theme.fontMono : Theme.font
                    font.pixelSize: root.focusFace ? 18 : 11; color: "#bdbdc5"
                }
                Row {
                    y: 62; spacing: 4
                    visible: S.IslandMedia.available
                    ActionButton {
                        objectName: "islandPrevious"; text: "‹"; font.pixelSize: 25
                        width: 28; height: 28; padding: 0; quiet: true; textColor: "white"
                        tooltip: "Previous track"; enabled: !!(S.IslandMedia.player && S.IslandMedia.player.canGoPrevious)
                        onClicked: S.IslandMedia.previous()
                    }
                    ActionButton {
                        id: play; objectName: "islandPlay"
                        iconName: S.IslandMedia.playing ? "pause" : "play"; iconSize: 18
                        width: 32; height: 28; padding: 0; quiet: true; textColor: "white"
                        tooltip: S.IslandMedia.playing ? "Pause playback" : "Play"
                        enabled: !!(S.IslandMedia.player && S.IslandMedia.player.canTogglePlaying)
                        onClicked: S.IslandMedia.toggle()
                    }
                    ActionButton {
                        objectName: "islandNext"; text: "›"; font.pixelSize: 25
                        width: 28; height: 28; padding: 0; quiet: true; textColor: "white"
                        tooltip: "Next track"; enabled: !!(S.IslandMedia.player && S.IslandMedia.player.canGoNext)
                        onClicked: S.IslandMedia.next()
                    }
                }
            }
            Item {
                id: glanceTime
                objectName: "islandGlanceTime"
                x: parent.width - width - 2; y: 10
                width: 116; height: 88
                Label {
                    width: parent.width; height: 50; text: Qt.formatDateTime(S.Clock.date,"d")
                    horizontalAlignment: Text.AlignRight
                    font.family: Theme.font; font.pixelSize: 44; font.weight: Font.DemiBold; color: "#ffffff"
                }
                Label {
                    y: 54; width: parent.width; height: 16
                    text: Qt.formatDateTime(S.Clock.date,"dddd")
                    horizontalAlignment: Text.AlignRight; font.pixelSize: 10; color: "#d4d4d8"
                }
                Label {
                    y: 73; width: parent.width; height: 16
                    text: Qt.formatDateTime(S.Clock.date,"MMMM")
                    horizontalAlignment: Text.AlignRight; font.pixelSize: 11; color: "#a5a5b0"
                }
            }
            Item {
                objectName: "islandWeekStrip"
                x: 4; y: 4; width: Math.max(0, glanceTime.x - 24); height: 92
                visible: !S.IslandMedia.available && !root.focusFace
                Label { text: Qt.formatDateTime(S.Clock.date,"MMMM").toUpperCase(); font.pixelSize: 9; font.letterSpacing: 1.2; color: "#a5a5b0" }
                Row {
                    y: 23; spacing: Math.max(2,(parent.width - 150) / 4)
                    Repeater {
                        model: 5
                        Item {
                            required property int index
                            readonly property date day: new Date(S.Clock.date.getFullYear(), S.Clock.date.getMonth(), S.Clock.date.getDate() + index - 2)
                            width: 30; height: 68
                            Label { width: parent.width; text: Qt.formatDateTime(parent.day,"ddd").slice(0,parent.index===2?3:1); horizontalAlignment:Text.AlignHCenter; font.pixelSize:9; color:parent.index===2?"#ffffff":"#85858f" }
                            Label { y:19; width:parent.width; text:Qt.formatDateTime(parent.day,"d");horizontalAlignment:Text.AlignHCenter;font.pixelSize:24;font.weight:parent.index===2?Font.DemiBold:Font.Normal;color:parent.index===2?"#ffffff":"#85858f" }
                            Rectangle { x:9;y:55;width:12;height:2;radius:1;color:"#ffffff";visible:parent.index===2 }
                        }
                    }
                }
            }
            Slider {
                id: seek
                objectName: "islandSeek"
                y: 104; width: parent.width; height: 18
                from: 0; to: Math.max(1, root.mediaLength)
                value: root.mediaPosition
                visible: S.IslandMedia.available
                enabled: !!(S.IslandMedia.player && S.IslandMedia.player.canSeek && root.mediaLength > 0)
                Accessible.name: "Track position"
                onMoved: S.IslandMedia.seek(value)
                background: Rectangle {
                    x: seek.leftPadding; y: (seek.height - height) / 2
                    width: seek.availableWidth; height: 3; radius: 1.5; color: "#343438"
                    Rectangle { width: seek.visualPosition * parent.width; height: parent.height; radius: 1.5; color: "#ffffff" }
                }
                handle: Rectangle {
                    x: seek.leftPadding + seek.visualPosition * (seek.availableWidth - width)
                    y: (seek.height - height) / 2
                    width: seek.activeFocus || seek.pressed ? 9 : 5; height: width; radius: width / 2
                    color: seek.activeFocus ? Theme.accentBlue : "white"
                }
            }
            Item {
                y: 132; width: parent.width; height: 30
                Label {
                    width: Math.max(0, parent.width - 190); height: parent.height
                    text: root.app.focusRunning ? "Focus  " + root.duration(root.remaining) : "Make room for focus"
                    font.pixelSize: 11; color: "#d4d4d8"
                }
                Row {
                    anchors.right: parent.right
                    spacing: 5
                    ActionButton {
                        id: focusToggle
                        objectName: "islandFocusToggle"
                        width: 62; height: 28; leftPadding: 6; rightPadding: 6
                        text: root.app.focusRunning ? "Pause" : "Start"; font.pixelSize: 11; textColor: "white"; quiet: true
                        tooltip: root.app.focusRunning ? "Pause focus session" : "Start focus session"
                        onClicked: { if (root.app.focusRunning) root.app.focusPause(); else root.app.focusStart(); }
                    }
                    ActionButton {
                        objectName: "islandFocusReset"
                        width: 48; height: 28; leftPadding: 4; rightPadding: 4
                        text: "Reset"; font.pixelSize: 11; textColor: "white"; quiet: true
                        tooltip: "Reset focus session to 25 minutes"
                        onClicked: root.app.focusReset(25)
                    }
                    ActionButton {
                        id: calendar
                        objectName: "islandCalendar"
                        iconName: "calendar"; iconSize: 14
                        width: 28; height: 28; padding: 0; quiet: true; textColor: "white"
                        tooltip: "Open calendar"; onClicked: root.calendarRequested()
                    }
                    ActionButton {
                        objectName: "islandMedia"
                        iconName: "music"; iconSize: 14
                        width: 28; height: 28; padding: 0; quiet: true; textColor: "white"
                        tooltip: "Open media controls"; onClicked: root.mediaRequested()
                    }
                }
            }
        }

        IslandNotificationPreview {
            id: notificationPreview
            x: (parent.width - width) / 2; y: root.headerHeight + 8
            width: Math.max(0, root.notificationPreferredWidth - 40)
            height: Math.max(0, root.bodyHeight - y - 12)
            visible: !!root.notification && !root.pinned
            active: root.interactive && visible
            entry: root.notification
            onOpenRequested: root.sectionRequested("inbox")
            onDismissRequested: { if (root.notification) S.Notifications.dismiss(root.notification.id); }
        }
        Item {
            x: 22; y: root.headerHeight + 14
            width: Math.max(0, parent.width - 44); height: 104
            visible: root.alertPreview && !root.notification && !root.pinned
            Label { width: parent.width - 32; text: root.eventLabel; font.pixelSize: 18; font.weight: Font.DemiBold; color: "white"; wrapMode: Text.Wrap; maximumLineCount: 2 }
            ActionButton { anchors.right: parent.right; width: 28; height: 28; text: "×"; quiet: true; tooltip: "Dismiss alert"; onClicked: root.eventDismissRequested() }
            ActionButton { y: 60; text: root.eventKind.indexOf("battery") >= 0 ? "Power controls" : "Open dashboard"; quiet: true; onClicked: root.sectionRequested(root.eventSection) }
        }
        Item {
            x: 22; y: root.headerHeight + 14; width: Math.max(0, parent.width - 44); height: 150
            visible: root.open && !root.pinned && !root.hasEvent && !root.assistantAutoOutput && root.activity === "thursday"
            Label { width: Math.max(0, parent.width - hoverSpeechOrb.width - 12); text: "Thursday · " + root.assistantLabel; elide: Text.ElideRight; color: "white"; font.weight: Font.DemiBold }
            Native.SpeechOrb { id: hoverSpeechOrb; objectName: "islandThursdayHoverOrb"; anchors.right: parent.right; y: root.voiceOrbCenterY - parent.y - height / 2; width: Math.min(120, parent.width * 0.36, parent.height - 16); height: width; active: root.assistantRecording || root.assistantSpeaking; processing: root.assistantProcessing; effectsActive: root.effectsActive; level: root.assistantLevel; reducedMotion: Theme.effectiveReducedMotion }
            Label { y: 31; width: Math.max(0, parent.width - hoverSpeechOrb.width - 12); text: root.assistantText; color: "#bdc0cc"; maximumLineCount: 3; wrapMode: Text.Wrap }
            ActionButton { y: 104; text: "Open Thursday"; quiet: true; onClicked: root.sectionRequested("thursday") }
        }
        IslandMusicPreview {
            id: musicPreview
            objectName: "islandMusicPreview"
            x: animatedAlbum.x + animatedAlbum.width + 16; y: root.headerInset + 90
            width: Math.max(0, parent.width - x - 20)
            height: 24
            showTransport: false
            showFooter: false
            visible: root.musicExpanded
            active: visible && root.effectsActive
            mediaPosition: root.mediaPosition
            samples: root.samples
            onDetailsRequested: root.sectionRequested("media")
        }
        IslandVoicePreview {
            id: assistantOutput
            objectName: "islandAssistantOutput"
            x: 20; y: root.headerHeight + 8
            width: Math.max(0, parent.width - 40)
            height: Math.max(0, root.bodyHeight - y - 12)
            active: root.assistantAutoOutput && root.effectsActive
            orbCenterY: root.voiceOrbCenterY - assistantOutput.y
            level: root.assistantLevel
            partialTranscript: root.assistantBackend && typeof root.assistantBackend.partialTranscript !== "undefined" ? root.assistantBackend.partialTranscript : root.assistantText
            finalTranscript: root.assistantBackend && typeof root.assistantBackend.finalTranscript !== "undefined" ? root.assistantBackend.finalTranscript : ""
            answer: root.assistantBackend ? root.assistantBackend.latestAnswer || "" : root.assistantText
            phase: !root.assistantBackend ? "listening" : root.assistantBackend.voiceError ? "error" : root.assistantRecording ? "listening" : root.assistantBackend.voiceState === "transcribing" ? "transcribing" : root.assistantSpeaking ? "speaking" : root.assistantBackend.latestAnswer ? "reply" : "thinking"
            onOpenRequested: root.sectionRequested("thursday")
        }
        Item {
            id: dashboardFrame
            objectName: "islandDashboardFrame"
            x: 20; y: root.headerHeight + 8
            width: Math.max(0, parent.width - 40)
            height: Math.max(0, root.bodyHeight - y - 18)
            visible: root.pinned
            opacity: !root.dashboardReady ? 0 : root.revealPending ? Math.max(0, 1 - root.shapeDistance / 180) : 1
            // Transient feedback already lives in the fixed clock header.
            // Never insert a status row into the pinned dashboard geometry.
            Loader {
                id: dashboard
                objectName: "islandDashboardLoader"
                x: (parent.width - width) / 2
                y: 0
                width: Math.max(0, Math.min(root.requestedWidth, root.maximumWidth) - 40)
                height: Math.max(0, Math.min(root.requestedHeight, root.maximumHeight) - root.headerHeight - 26)
                active: true
                onLoaded: {
                    root.dashboardReady = false;
                    root.layoutStableFrames = 0;
                    root.lastLayoutHeight = -1;
                    root.queueLayout();
                }
                sourceComponent: IslandDesk {
                    app: root.app; screenInfo: root.screenInfo; headerEmbedded: true
                    section: root.section; active: root.pinned && root.effectsActive
                    now: root.now; mediaPosition: root.mediaPosition; spectrumSamples: S.Spectrum.samples
                    onSectionRequested: section => root.sectionRequested(section)
                    onDismissRequested: root.dismissRequested()
                    onOpenPanelRequested: panel => root.openPanelRequested(panel)
                    onSettingsRequested: section => root.settingsRequested(section)
                    onCaptureRequested: annotate => root.captureRequested(annotate)
                    onRecordingRequested: root.recordingRequested()
                    onThursdayFullChatRequested: root.thursdayFullChatRequested()
                }
            }
        }
    }
}
