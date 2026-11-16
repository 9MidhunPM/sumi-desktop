pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import "config"
import "services" as S
import "components" as C
import "widgets" as W
import "widgets/WidgetLayout.js" as WidgetLayout

PanelWindow {
    id: root
    required property var modelData
    required property var app
    screen: modelData
    color: "transparent"
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "sumi-widgets"
    WlrLayershell.layer: WlrLayer.Bottom
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

    readonly property var flags: S.Widgets.document.enabled || ({})
    readonly property bool chosen: !!modelData && modelData === app.widgetScreen
    readonly property var monitor: Hyprland.monitors.values.find(candidate => candidate && modelData && candidate.name === modelData.name) || null
    readonly property bool occluded: !!(monitor && monitor.activeWorkspace && monitor.activeWorkspace.hasFullscreen)
    readonly property bool anyEnabled: ["clock", "spotify", "priorities", "deadline"].some(key => WidgetLayout.enabled(flags, key))
    readonly property bool eligible: chosen && anyEnabled && !occluded
    readonly property bool idle: idleMonitor.isIdle
    readonly property bool powerSaving: S.Battery.onBattery || S.Battery.profile === "power-saver"
    readonly property var geometry: WidgetLayout.layout(S.Widgets.scene, width, height, S.Widgets.layoutMode, flags)
    readonly property bool compact: geometry.compact
    readonly property real widgetScale: geometry.scale
    readonly property var widgetStyle: S.Widgets.scene.layout && S.Widgets.scene.layout.widgetStyle || ({})
    readonly property bool darkClock: S.Widgets.scene.layout && S.Widgets.scene.layout.clockTone === "dark"
    readonly property color clockText: widgetStyle.clockInk || (darkClock ? "#14202b" : "#eaf4ff")
    readonly property color clockAccent: widgetStyle.clockAccent || (darkClock ? "#633142" : Theme.accentCyan)
    readonly property int moveDuration: !visible || idle || Theme.effectiveReducedMotion ? 0 : Theme.batteryMotion ? 140 : 650
    property bool initialized: false
    property bool settling: false
    readonly property bool moving: clockX.running || clockY.running || musicX.running || musicY.running
        || prioritiesX.running || prioritiesY.running || deadlineX.running || deadlineY.running
    property string artworkSource: ""
    visible: eligible
    function refreshArtwork() {
        if (eligible && !idle && WidgetLayout.enabled(flags, "spotify")) artworkSource = S.WidgetMedia.artUrl;
    }
    onEligibleChanged: { refreshArtwork(); if (!eligible) finishMovement(); }
    onIdleChanged: { refreshArtwork(); if (idle) finishMovement(); }
    onFlagsChanged: refreshArtwork()
    onWidthChanged: finishMovement()
    onHeightChanged: finishMovement()
    onModelDataChanged: Qt.callLater(finishMovement)
    Component.onCompleted: Qt.callLater(() => { root.initialized = true; root.refreshArtwork(); })
    Connections { target: S.WidgetMedia; function onArtUrlChanged() { root.refreshArtwork(); } }
    Connections { target: Theme; function onEffectiveReducedMotionChanged() { if (Theme.effectiveReducedMotion) root.finishMovement(); } }
    function finishMovement() {
        if (!initialized) return;
        // Behavior-owned animations do not obey complete() like standalone
        // animations. Rebind the destination with Behaviors disabled so an
        // idle/fullscreen transition also cancels the in-flight render work.
        settling = true;
        const entries = [{item: clockCard, key: "clock"}, {item: musicCard, key: "spotify"},
            {item: prioritiesCard, key: "priorities"}, {item: deadlineCard, key: "deadline"}];
        entries.forEach(entry => {
            entry.item.x = Qt.binding(() => root.geometry[entry.key].x);
            entry.item.y = Qt.binding(() => root.geometry[entry.key].y);
        });
        settling = false;
    }

    IdleMonitor { id: idleMonitor; enabled: root.chosen; timeout: 60; respectInhibitors: false }
    Binding {
        target: S.WidgetMedia
        property: "displayActive"
        value: root.eligible && !root.idle && WidgetLayout.enabled(root.flags, "spotify")
    }
    // The rest of the desktop remains click-through. The masks follow the
    // animated cards; no full-screen input area or keyboard focus is acquired.
    mask: Region {
        Region { x: clockCard.x; y: clockCard.y; width: clockCard.visible ? clockCard.width : 0; height: clockCard.visible ? clockCard.height : 0 }
        Region { x: musicCard.x; y: musicCard.y; width: musicCard.visible ? musicCard.width : 0; height: musicCard.visible ? musicCard.height : 0 }
        Region { x: prioritiesCard.x; y: prioritiesCard.y; width: prioritiesCard.visible ? prioritiesCard.width : 0; height: prioritiesCard.visible ? prioritiesCard.height : 0 }
        Region { x: deadlineCard.x; y: deadlineCard.y; width: deadlineCard.visible ? deadlineCard.width : 0; height: deadlineCard.visible ? deadlineCard.height : 0 }
    }

    function edit() { app.open("widgets", modelData); }

    W.WidgetCard {
        id: clockCard
        objectName: "desktopClock"
        x: root.geometry.clock.x; y: root.geometry.clock.y
        width: root.geometry.clock.width; height: root.geometry.clock.height
        uiScale: root.widgetScale
        surface: false
        visible: WidgetLayout.enabled(root.flags, "clock")
        Behavior on x { enabled: root.initialized && !root.settling; NumberAnimation { id: clockX; duration: root.moveDuration; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bounceCurve } }
        Behavior on y { enabled: root.initialized && !root.settling; NumberAnimation { id: clockY; duration: root.moveDuration; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bounceCurve } }

        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.app.open("calendar", root.modelData) }
        // Measured directly from Eww's GTK allocations. The clock's 14px
        // bottom margin is included in this 520x222 footprint.
        Repeater {
            model: [S.Clock.hour.length === 1 ? "0" + S.Clock.hour : S.Clock.hour, ":", S.Clock.minute]
            C.Label {
                required property string modelData
                required property int index
                objectName: "desktopClockDigit" + index
                x: [4, 199, 247][index]; y: 2
                width: [193, 48, 193][index]; height: 210
                leftPadding: index === 1 ? 8 : 0
                rightPadding: index === 1 ? 8 : 0
                text: modelData
                color: index === 1 ? root.clockAccent : root.clockText
                font.family: Theme.font; font.features: IslandStyle.figures
                font.pixelSize: index === 1 ? 136 : 160
                // The proportional face is wider than the old mono cells: fit, never elide.
                elide: Text.ElideNone; fontSizeMode: Text.HorizontalFit; minimumPixelSize: 90
                font.weight: index === 1 ? Font.Medium : Font.Black
                horizontalAlignment: Text.AlignHCenter
                Accessible.ignored: true
                layer.enabled: GraphicsInfo.api !== GraphicsInfo.Software
                layer.effect: MultiEffect {
                    shadowEnabled: true
                    shadowColor: "#081430"
                    shadowOpacity: 0.3
                    shadowVerticalOffset: 4
                    blurMax: 14
                    shadowBlur: 1
                }
            }
        }
        C.Label {
            objectName: "desktopClockPeriod"
            x: 442; y: 2; width: 78; height: 210
            leftPadding: 8; topPadding: 24
            text: S.Clock.period
            elide: Text.ElideNone
            color: root.widgetStyle.clockPeriod || root.clockAccent
            font.family: Theme.font; font.features: IslandStyle.figures
            font.pixelSize: 48
            font.weight: Font.Bold
            layer.enabled: GraphicsInfo.api !== GraphicsInfo.Software
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: "#081430"
                shadowOpacity: 0.26
                shadowVerticalOffset: 3
                blurMax: 10
                shadowBlur: 1
            }
        }
        Accessible.role: Accessible.Button
        Accessible.name: S.Clock.accessibleTime + ", " + S.Clock.dateLabel + ". Open calendar"
        Accessible.onPressAction: root.app.open("calendar", root.modelData)
    }

    W.WidgetCard {
        id: musicCard
        objectName: "desktopSpotify"
        x: root.geometry.spotify.x; y: root.geometry.spotify.y
        width: root.geometry.spotify.width; height: root.geometry.spotify.height
        uiScale: root.widgetScale
        surface: false
        panelColor: root.widgetStyle.cardFill || Qt.rgba(Theme.desktopBackground.r, Theme.desktopBackground.g, Theme.desktopBackground.b, 0.82)
        mainText: root.widgetStyle.text || Theme.textMain
        secondaryText: root.widgetStyle.muted || Theme.textSoft
        readonly property color accent: root.widgetStyle.accent || Theme.accentBlue
        readonly property color outline: root.widgetStyle.cardBorder || Qt.rgba(Theme.accentPink.r, Theme.accentPink.g, Theme.accentPink.b, 0.24)
        visible: WidgetLayout.enabled(root.flags, "spotify")
        Behavior on x { enabled: root.initialized && !root.settling; NumberAnimation { id: musicX; duration: root.moveDuration; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bounceCurve } }
        Behavior on y { enabled: root.initialized && !root.settling; NumberAnimation { id: musicY; duration: root.moveDuration; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bounceCurve } }

        RectangularShadow {
            anchors.fill: parent
            radius: 20; blur: 24; offset: Qt.vector2d(0, 8)
            color: "#29060e1e"
            visible: GraphicsInfo.api !== GraphicsInfo.Software
        }
        Rectangle {
            anchors.fill: parent
            radius: 20
            color: musicCard.panelColor
            border.width: 1.5
            border.color: musicCard.outline
        }
        Rectangle {
            id: album
            objectName: "desktopSpotifyAlbum"
            x: 11; y: 11
            width: 160; height: 160
            radius: 18
            color: Qt.rgba(musicCard.accent.r, musicCard.accent.g, musicCard.accent.b, 0.12)
            clip: true
            C.Icon {
                objectName: "desktopSpotifyArtworkFallback"
                anchors.centerIn: parent; name: "music"; size: 48
                color: musicCard.mainText
                visible: artwork.status !== Image.Ready
            }
            C.ArtworkImage {
                id: artwork
                objectName: "desktopSpotifyArtwork"
                anchors.fill: parent
                artworkUrl: root.artworkSource
                active: root.eligible && !root.idle && WidgetLayout.enabled(root.flags, "spotify")
                sourceSize: Qt.size(320, 320)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: true
                visible: status === Image.Ready && GraphicsInfo.api === GraphicsInfo.Software
            }
            Item {
                id: albumMask
                anchors.fill: parent
                visible: false
                layer.enabled: true
                Rectangle { anchors.fill: parent; radius: 18; color: "white" }
            }
            MultiEffect {
                anchors.fill: parent
                source: artwork
                maskEnabled: true
                maskSource: albumMask
                visible: artwork.status === Image.Ready && GraphicsInfo.api !== GraphicsInfo.Software
            }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: S.WidgetMedia.openSpotify() }
            Accessible.role: Accessible.Button
            Accessible.name: "Open Spotify"
            Accessible.onPressAction: S.WidgetMedia.openSpotify()
        }
        Item {
            id: musicInfo
            x: 187; y: 1; width: 232; height: 181
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 8; height: 24
                spacing: 0
                C.Label {
                    objectName: "desktopSpotifyStatus"
                    text: S.WidgetMedia.available ? (S.WidgetMedia.playing ? "Playing" : "Paused") : "Offline"
                    font.family: Theme.font; font.pixelSize: 11; font.weight: Font.Bold
                    topPadding: 10; height: 24
                    color: musicCard.accent
                }
                C.Label { text: "•"; font.pixelSize: 11; leftPadding: 6; rightPadding: 6; topPadding: 10; height: 24; color: musicCard.secondaryText }
                C.Label { text: "Spotify"; font.family: Theme.font; font.pixelSize: 11; font.weight: Font.Bold; topPadding: 10; rightPadding: 4; height: 24; color: musicCard.secondaryText }
            }
            C.Label {
                objectName: "desktopSpotifyTitle"
                y: 32; width: parent.width; height: 26
                topPadding: 5; rightPadding: 16
                text: S.WidgetMedia.available ? S.WidgetMedia.title : "Nothing playing"
                color: musicCard.mainText
                font.family: Theme.font
                font.pixelSize: 16
                font.weight: Font.ExtraBold
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
            }
            C.Label {
                objectName: "desktopSpotifyArtist"
                y: 58; width: parent.width; height: 22
                topPadding: 5; rightPadding: 4
                text: S.WidgetMedia.available ? S.WidgetMedia.artist : "Spotify"
                font.family: Theme.font
                font.pixelSize: 12
                font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignHCenter
                color: musicCard.secondaryText
            }
            Row {
                x: 23; y: 90
                spacing: 0
                C.ActionButton {
                    id: previousButton
                    objectName: "desktopSpotifyPrevious"
                    iconName: "backward"; iconSize: 16; quiet: true
                    width: 62; height: 46
                    leftPadding: 5; rightPadding: 15; topPadding: 4; bottomPadding: 0
                    textColor: musicCard.mainText
                    background: Item {
                        Rectangle { x: 5; y: 4; width: 42; height: 42; radius: 10.5; color: previousButton.hovered ? Theme.bgPlaying : "transparent"; border.width: previousButton.visualFocus ? 1 : 0; border.color: musicCard.accent }
                    }
                    tooltip: "Previous Spotify track"
                    enabled: !!S.WidgetMedia.player && S.WidgetMedia.player.canGoPrevious
                    onClicked: S.WidgetMedia.previous()
                }
                C.ActionButton {
                    id: playButton
                    objectName: "desktopSpotifyPlay"
                    iconName: S.WidgetMedia.playing ? "pause-fill" : "play-fill"; iconSize: 18; quiet: true
                    width: 62; height: 46
                    leftPadding: 5; rightPadding: 15; topPadding: 4; bottomPadding: 0
                    textColor: musicCard.mainText
                    background: Item {
                        Rectangle { x: 5; y: 4; width: 42; height: 42; radius: 10.5; color: playButton.hovered ? Theme.bgPlaying : "transparent"; border.width: playButton.visualFocus ? 1 : 0; border.color: musicCard.accent }
                    }
                    tooltip: S.WidgetMedia.available ? (S.WidgetMedia.playing ? "Pause Spotify" : "Play Spotify") : "Open Spotify"
                    enabled: !S.WidgetMedia.available || (!!S.WidgetMedia.player && S.WidgetMedia.player.canTogglePlaying)
                    onClicked: { if (S.WidgetMedia.available) S.WidgetMedia.toggle(); else S.WidgetMedia.openSpotify(); }
                }
                C.ActionButton {
                    id: nextButton
                    objectName: "desktopSpotifyNext"
                    iconName: "forward"; iconSize: 16; quiet: true
                    width: 62; height: 46
                    leftPadding: 5; rightPadding: 15; topPadding: 4; bottomPadding: 0
                    textColor: musicCard.mainText
                    background: Item {
                        Rectangle { x: 5; y: 4; width: 42; height: 42; radius: 10.5; color: nextButton.hovered ? Theme.bgPlaying : "transparent"; border.width: nextButton.visualFocus ? 1 : 0; border.color: musicCard.accent }
                    }
                    tooltip: "Next Spotify track"
                    enabled: !!S.WidgetMedia.player && S.WidgetMedia.player.canGoNext
                    onClicked: S.WidgetMedia.next()
                }
            }
            Rectangle {
                objectName: "desktopSpotifyProgress"
                x: 12; y: 154; width: 200; height: 10; radius: 10
                color: Qt.rgba(musicCard.panelColor.r, musicCard.panelColor.g, musicCard.panelColor.b, 0.66)
                border.width: 1.5; border.color: musicCard.outline
                Rectangle {
                    objectName: "desktopSpotifyProgressFill"
                    height: parent.height - 3; y: 1.5; x: 1.5; radius: 10
                    width: (parent.width - 3) * Math.max(0, Math.min(1, S.WidgetMedia.position / Math.max(1, S.WidgetMedia.length)))
                    color: musicCard.accent
                }
            }
        }
    }

    W.WidgetCard {
        id: prioritiesCard
        objectName: "desktopPriorities"
        x: root.geometry.priorities.x; y: root.geometry.priorities.y
        width: root.geometry.priorities.width; height: root.geometry.priorities.height
        uiScale: root.widgetScale
        visible: WidgetLayout.enabled(root.flags, "priorities")
        Behavior on x { enabled: root.initialized && !root.settling; NumberAnimation { id: prioritiesX; duration: root.moveDuration; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bounceCurve } }
        Behavior on y { enabled: root.initialized && !root.settling; NumberAnimation { id: prioritiesY; duration: root.moveDuration; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bounceCurve } }

        C.Label { x: 18; y: 17; text: "Make room for"; font.pixelSize: 12; font.letterSpacing: 0; color: prioritiesCard.secondaryText; font.weight: Font.DemiBold }
        C.ActionButton {
            objectName: "desktopPrioritiesEdit"
            x: parent.width - 44; y: 8; width: 32; height: 30; padding: 0
            iconName: "more-horizontal"; iconSize: 18; quiet: true
            tooltip: "Edit desktop priorities and deadline"
            onClicked: root.edit()
        }
        Column {
            x: 15; y: 42
            width: parent.width - 30
            spacing: root.compact ? 0 : 4
            Repeater {
                model: 3
                delegate: CheckBox {
                    id: priority
                    required property int index
                    objectName: "desktopPriority" + index
                    readonly property var entry: (S.Widgets.document.priorities || [])[index] || ({text: "", done: false})
                    width: parent.width; height: 34
                    checked: !!entry.done
                    hoverEnabled: true
                    activeFocusOnTab: true
                    Accessible.name: entry.text || "Set priority " + (index + 1)
                    indicator: Rectangle {
                        x: 3; anchors.verticalCenter: parent.verticalCenter
                        width: 17; height: 17; radius: 8.5
                        color: priority.checked ? Theme.accentBlue : "transparent"
                        border.width: 1
                        border.color: priority.visualFocus || priority.hovered ? Theme.accentBlue : Theme.borderStrong
                        C.Label { anchors.centerIn: parent; text: priority.checked ? "✓" : ""; color: Theme.desktopBackground; font.pixelSize: 12; font.weight: Font.Bold }
                    }
                    contentItem: C.Label {
                        leftPadding: 31; rightPadding: 5
                        text: priority.entry.text || "Add a priority"
                        font.pixelSize: 12
                        font.strikeout: priority.checked
                        color: priority.checked || !priority.entry.text ? prioritiesCard.secondaryText : prioritiesCard.mainText
                    }
                    background: Rectangle { radius: 8; color: priority.hovered ? Qt.rgba(Theme.textMain.r, Theme.textMain.g, Theme.textMain.b, 0.05) : "transparent" }
                    onClicked: { if (entry.text) S.Widgets.togglePriority(index); else root.edit(); }
                }
            }
        }
    }

    W.WidgetCard {
        id: deadlineCard
        objectName: "desktopDeadline"
        x: root.geometry.deadline.x; y: root.geometry.deadline.y
        width: root.geometry.deadline.width; height: root.geometry.deadline.height
        uiScale: root.widgetScale
        visible: WidgetLayout.enabled(root.flags, "deadline")
        readonly property var deadline: S.Widgets.document.deadline || ({})
        readonly property bool overdue: typeof deadline.at === "number" && deadline.at < S.Clock.date.getTime()
        Behavior on x { enabled: root.initialized && !root.settling; NumberAnimation { id: deadlineX; duration: root.moveDuration; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bounceCurve } }
        Behavior on y { enabled: root.initialized && !root.settling; NumberAnimation { id: deadlineY; duration: root.moveDuration; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bounceCurve } }

        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.edit() }
        C.Label {
            x: 18; y: 14; width: parent.width - 36
            text: deadlineCard.deadline.title || "Your next milestone"
            font.pixelSize: 11; color: deadlineCard.secondaryText
        }
        C.Label {
            objectName: "desktopDeadlineValue"
            x: 18; y: 38; width: parent.width - 36
            text: S.Widgets.deadlineText
            font.family: Theme.fontMono; font.pixelSize: deadlineCard.overdue ? 21 : 25
            font.letterSpacing: -1; font.weight: Font.Medium
            color: deadlineCard.overdue ? deadlineCard.warningText : deadlineCard.mainText
        }
        C.Label {
            x: 18; y: 76; width: parent.width - 36
            text: deadlineCard.deadline.at ? Qt.formatDateTime(new Date(deadlineCard.deadline.at), "ddd, d MMM · h:mm AP") : "A date to look forward to · click to set"
            font.pixelSize: 11; color: deadlineCard.secondaryText
        }
        Accessible.role: Accessible.Button
        Accessible.name: (deadlineCard.deadline.title || "Personal deadline") + ", " + S.Widgets.deadlineText + ". Edit deadline"
        Accessible.onPressAction: root.edit()
    }
}
