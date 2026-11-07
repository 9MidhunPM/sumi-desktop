pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import Quickshell.Widgets
import "../config"
import "../services" as S

// Pure visual content. The native host owns geometry, focus and demand gates.
FocusScope {
    id: root
    focus: pinned
    required property var app
    property var screenInfo: null
    property bool notch: false
    property bool open: false
    property bool pinned: false
    property bool interactive: true
    property bool effectsActive: true
    property real bodyWidth: 176
    property real bodyHeight: 32
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
    property var assistantSamples: []
    readonly property real assistantPreferredHeight: assistantOutput.implicitHeight + headerHeight + 20
    property string assistantLabel: ""
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
    readonly property real preferredWidth: dashboard.item ? dashboard.item.preferredWidth : 640
    readonly property real preferredHeight: dashboard.item ? dashboard.item.preferredHeight + headerHeight + 26 : 560
    property var samples: activity === "thursday" ? assistantSamples : S.Spectrum.samples
    readonly property alias surface: blackBody
    readonly property alias headerSurface: headerBackground
    readonly property alias leftFillet: leftShoulder
    readonly property alias rightFillet: rightShoulder
    readonly property bool focusFace: !S.IslandMedia.available && !!app.focusRunning
    readonly property var firstControl: S.IslandMedia.available ? play : focusToggle
    readonly property real headerInset: notch ? 4 : 0
    readonly property real headerHeight: headerInset + 36
    readonly property real headerWidth: Math.min(bodyWidth, headerRoom)
    readonly property bool wideBody: bodyWidth > headerRoom + 0.1
    readonly property bool hasEvent: eventKind.length > 0
    readonly property bool hasFlanks: headerWidth >= 260
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
        if (firstControl && firstControl.enabled) firstControl.forceActiveFocus(Qt.OtherFocusReason);
        else calendar.forceActiveFocus(Qt.OtherFocusReason);
    }
    Keys.onEscapePressed: event => { dismissRequested(); event.accepted = true; }

    Rectangle {
        id: blackBody
        objectName: "islandBody"
        x: (root.width - root.bodyWidth) / 2
        y: root.wideBody ? root.headerHeight : 0
        width: root.bodyWidth
        height: Math.max(0, root.bodyHeight - y)
        radius: root.open ? 28 : root.notch ? 20 : 18
        topLeftRadius: root.notch && !root.wideBody ? 0 : radius
        topRightRadius: root.notch && !root.wideBody ? 0 : radius
        color: "transparent"
    }
    Rectangle {
        id: headerBackground
        x: (root.width - width) / 2
        width: root.headerWidth; height: root.headerHeight
        radius: root.notch ? 20 : 18
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
                Accessible.name: (root.pinned ? "Unpin" : "Pin") + " dynamic island, " + root.timeText + " " + root.periodText
            }
            Label {
                id: clock
                objectName: "barClockTime"
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
                x: 14; height: 24
                anchors.verticalCenter: parent.verticalCenter
                width: Math.max(0, clock.x - x - 16)
                visible: root.hasFlanks
                clip: true
                ArtworkImage {
                    id: smallArt
                    width: 24; height: 24
                    artworkUrl: S.IslandMedia.artUrl
                    active: root.effectsActive && root.activity === "media" && !root.hasEvent && leftFlank.visible
                    visible: root.activity === "media" && !root.hasEvent && status === Image.Ready
                    sourceSize: Qt.size(48, 48)
                    fillMode: Image.PreserveAspectCrop
                }
                Icon {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.hasEvent || root.activity === "capture" || root.activity === "thursday" || root.activity === "recording" || (root.activity === "media" && smallArt.status !== Image.Ready)
                    name: root.activity === "capture" ? "camera" : root.eventKind === "notification" ? "bell" : root.eventKind === "brightness" ? "settings" : root.activity === "thursday" || root.eventKind === "thursday" ? "sparkles" : root.activity === "recording" || root.eventKind === "recording" ? "record" : root.eventKind === "volume" || root.eventKind === "mute" ? (S.Audio.muted ? "volume-x" : "volume") : root.eventKind === "microphone" ? "volume-x" : root.eventKind === "power" ? (S.Battery.charging ? "battery-charging" : "battery") : (root.eventKind === "low-battery" || root.eventKind === "critical-battery") ? "battery" : root.activity === "focus" || root.eventKind.indexOf("focus") >= 0 ? "calendar" : "music"
                    size: 14
                    color: (root.eventKind === "low-battery" || root.eventKind === "critical-battery" || root.activity === "recording") ? Theme.accentWarn : "#ffffff"
                }
                Label {
                    x: root.activity === "focus" && !root.hasEvent ? 0 : 21
                    width: parent.width - x
                    height: parent.height
                    text: root.hasEvent ? root.eventLabel : root.activity === "focus" ? root.duration(root.remaining) : root.activity === "capture" ? "Select region" : root.activity === "recording" ? "Recording" : root.activity === "thursday" ? root.assistantLabel : ""
                    font.pixelSize: 10
                    font.weight: Font.Medium
                    color: "#e4e4e7"
                    verticalAlignment: Text.AlignVCenter
                }
            }
            Item {
                id: rightFlank
                x: period.x + period.width + 16
                width: Math.max(0, parent.width - x - 14)
                height: 14
                anchors.verticalCenter: parent.verticalCenter
                clip: true
                visible: root.hasFlanks
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
                    anchors.fill: parent
                    spacing: 1
                    visible: !root.hasEvent && (root.activity === "media" || root.activity === "thursday")
                    Repeater {
                        model: 20
                        Rectangle {
                            required property int index
                            objectName: "islandWave" + index
                            width: Math.max(0, (rightFlank.width - 19) / 20)
                            height: Math.max(2, Math.min(100, Math.max(0, Number(root.samples[index]) || 0)) * 0.14)
                            y: rightFlank.height - height
                            radius: 1
                            color: "#f4f4f5"
                            Behavior on height { NumberAnimation { duration: Theme.effectiveReducedMotion ? 0 : 90; easing.type: Easing.OutQuad } }
                        }
                    }
                }
            }
        }

        Item {
            id: details
            objectName: "islandDetails"
            x: 16; y: root.headerInset + 46
            width: Math.max(0, parent.width - 32)
            height: 164
            opacity: root.open && !root.pinned && !root.notification && !root.alertPreview && root.activity !== "thursday" && !root.assistantAutoOutput ? 1 : 0
            visible: opacity > 0.001
            enabled: root.interactive && root.open
            onVisibleChanged: if (visible && root.pinned) Qt.callLater(root.focusDefault)
            Behavior on opacity { NumberAnimation { duration: Theme.effectiveReducedMotion ? 0 : root.open ? Theme.motionEnter : Theme.motionExit } }

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

        Rectangle {
            x: header.x + header.width - 10; y: root.headerInset + 6
            width: 5; height: 5; radius: 2.5
            visible: root.criticalAttention || root.unread > 0
            color: root.criticalAttention ? Theme.accentWarn : "#d4d4d8"
        }
        IslandNotificationPreview {
            x: 20; y: root.headerHeight + 8
            width: Math.max(0, parent.width - 40)
            height: Math.max(0, root.bodyHeight - y - 12)
            visible: !!root.notification && !root.pinned
            active: root.interactive && visible
            entry: root.notification
            onOpenRequested: root.sectionRequested("inbox")
            onDismissRequested: root.eventDismissRequested()
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
            Label { text: "Thursday · " + root.assistantLabel; color: "white"; font.weight: Font.DemiBold }
            Label { y: 31; width: parent.width; text: root.assistantText; color: "#bdc0cc"; maximumLineCount: 3; wrapMode: Text.Wrap }
            ActionButton { y: 104; text: "Open Thursday"; quiet: true; onClicked: root.sectionRequested("thursday") }
        }
        IslandAssistantOutput {
            id: assistantOutput
            objectName: "islandAssistantOutput"
            x: 20; y: root.headerHeight + 10
            width: Math.max(0, parent.width - 40)
            height: Math.max(0, root.bodyHeight - y - 10)
            text: root.assistantText
            samples: root.assistantSamples
            speaking: root.assistantSpeaking
            active: root.assistantAutoOutput && root.effectsActive
            visible: root.assistantAutoOutput
        }
        Item {
            id: dashboardFrame
            objectName: "islandDashboardFrame"
            x: 20; y: root.headerHeight + 8
            width: Math.max(0, parent.width - 40)
            height: Math.max(0, root.bodyHeight - y - 18)
            visible: root.pinned
            // Transient feedback already lives in the fixed clock header.
            // Never insert a status row into the pinned dashboard geometry.
            Loader {
                id: dashboard
                objectName: "islandDashboardLoader"
                y: 0
                width: parent.width; height: Math.max(0, parent.height - y)
                active: root.pinned
                sourceComponent: IslandDashboard {
                    app: root.app; screenInfo: root.screenInfo
                    section: root.section; active: root.pinned && root.effectsActive
                    now: root.now; mediaPosition: root.mediaPosition
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
    IslandTabGesture {
        anchors.fill: parent
        z: 2000
        deck: dashboard.item ? dashboard.item.tabDeck : null
        active: root.pinned && root.interactive
    }
}
