pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
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
    readonly property bool darkClock: S.Widgets.scene.layout && S.Widgets.scene.layout.clockTone === "dark"
    readonly property color clockText: darkClock ? "#14202b" : "#f5f3ec"
    readonly property color clockAccent: darkClock ? "#633142" : Theme.accentPink
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
        Behavior on x { enabled: root.initialized && !root.settling; NumberAnimation { id: clockX; duration: root.moveDuration; easing.type: Easing.OutQuint } }
        Behavior on y { enabled: root.initialized && !root.settling; NumberAnimation { id: clockY; duration: root.moveDuration; easing.type: Easing.OutQuint } }

        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.app.open("calendar", root.modelData) }
        C.Label {
            x: 0; y: root.compact ? 0 : 4
            width: parent.width
            text: Qt.formatDateTime(S.Clock.date, "dddd").toUpperCase()
            color: root.clockText
            font.pixelSize: root.compact ? 11 : 12
            font.letterSpacing: 3.5
            font.weight: Font.DemiBold
            style: root.darkClock ? Text.Normal : Text.Outline; styleColor: "#60000000"
        }
        Row {
            x: -5; y: root.compact ? 16 : 22
            spacing: 12
            Row {
                spacing: -4
                Repeater {
                    model: [S.Clock.hour, ":", S.Clock.minute]
                    C.Label {
                        required property string modelData
                        required property int index
                        text: modelData
                        color: index === 1 ? root.clockAccent : root.clockText
                        font.family: Theme.fontMono
                        font.pixelSize: root.compact ? 62 : 86
                        font.weight: Font.DemiBold
                        font.letterSpacing: -3
                        style: root.darkClock ? Text.Normal : Text.Outline; styleColor: "#50000000"
                        Accessible.ignored: true
                    }
                }
            }
            C.Label {
                anchors.bottom: parent.bottom
                anchors.bottomMargin: root.compact ? 12 : 17
                text: S.Clock.period.toLowerCase()
                color: root.clockText
                font.pixelSize: root.compact ? 14 : 18
                font.weight: Font.Medium
                style: root.darkClock ? Text.Normal : Text.Outline; styleColor: "#60000000"
            }
        }
        C.Label {
            x: 0; y: root.compact ? 91 : 125
            width: parent.width
            text: Qt.formatDateTime(S.Clock.date, "d MMMM yyyy")
            color: root.clockText
            font.pixelSize: root.compact ? 12 : 14
            font.letterSpacing: 1
            style: root.darkClock ? Text.Normal : Text.Outline; styleColor: "#60000000"
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
        visible: WidgetLayout.enabled(root.flags, "spotify")
        Behavior on x { enabled: root.initialized && !root.settling; NumberAnimation { id: musicX; duration: root.moveDuration; easing.type: Easing.OutQuint } }
        Behavior on y { enabled: root.initialized && !root.settling; NumberAnimation { id: musicY; duration: root.moveDuration; easing.type: Easing.OutQuint } }

        Rectangle {
            id: album
            x: 16; y: 16
            width: root.compact ? 76 : 108; height: width
            radius: 13
            color: Qt.rgba(Theme.accentBlue.r, Theme.accentBlue.g, Theme.accentBlue.b, 0.15)
            clip: true
            C.Icon { anchors.centerIn: parent; name: "music"; size: root.compact ? 30 : 40; color: Theme.accentBlue }
            Image {
                objectName: "desktopSpotifyArtwork"
                anchors.fill: parent
                source: root.artworkSource
                sourceSize: Qt.size(216, 216)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: true
                visible: status === Image.Ready
            }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: S.WidgetMedia.openSpotify() }
            Accessible.role: Accessible.Button
            Accessible.name: "Open Spotify"
            Accessible.onPressAction: S.WidgetMedia.openSpotify()
        }
        Item {
            id: musicInfo
            x: album.x + album.width + 16; y: 16
            width: parent.width - x - 16
            height: parent.height - 30
            Row {
                spacing: 6
                Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 5; height: 5; radius: 3; color: S.WidgetMedia.playing ? Theme.accentCyan : Theme.textSoft }
                C.Label { text: "SPOTIFY"; font.pixelSize: 9; font.letterSpacing: 2; color: musicCard.secondaryText; font.weight: Font.DemiBold }
            }
            C.Label {
                objectName: "desktopSpotifyTitle"
                y: root.compact ? 20 : 25; width: parent.width
                text: S.WidgetMedia.available ? S.WidgetMedia.title : "A little music?"
                color: musicCard.mainText
                font.pixelSize: root.compact ? 14 : 17
                font.weight: Font.DemiBold
            }
            C.Label {
                y: root.compact ? 41 : 51; width: parent.width
                text: S.WidgetMedia.available ? S.WidgetMedia.artist : "Open Spotify to begin"
                font.pixelSize: root.compact ? 11 : 12
                color: musicCard.secondaryText
            }
            Row {
                y: root.compact ? 62 : 77
                spacing: root.compact ? 3 : 9
                C.ActionButton {
                    objectName: "desktopSpotifyPrevious"
                    text: "‹"; font.pixelSize: 27; quiet: true
                    width: 32; height: 32; padding: 0
                    textColor: musicCard.mainText
                    tooltip: "Previous Spotify track"
                    enabled: !!S.WidgetMedia.player && S.WidgetMedia.player.canGoPrevious
                    onClicked: S.WidgetMedia.previous()
                }
                C.ActionButton {
                    objectName: "desktopSpotifyPlay"
                    iconName: S.WidgetMedia.playing ? "pause" : "play"; iconSize: 17
                    selected: true; width: 34; height: 32; padding: 0
                    tooltip: S.WidgetMedia.available ? (S.WidgetMedia.playing ? "Pause Spotify" : "Play Spotify") : "Open Spotify"
                    enabled: !S.WidgetMedia.available || (!!S.WidgetMedia.player && S.WidgetMedia.player.canTogglePlaying)
                    onClicked: { if (S.WidgetMedia.available) S.WidgetMedia.toggle(); else S.WidgetMedia.openSpotify(); }
                }
                C.ActionButton {
                    objectName: "desktopSpotifyNext"
                    text: "›"; font.pixelSize: 27; quiet: true
                    width: 32; height: 32; padding: 0
                    textColor: musicCard.mainText
                    tooltip: "Next Spotify track"
                    enabled: !!S.WidgetMedia.player && S.WidgetMedia.player.canGoNext
                    onClicked: S.WidgetMedia.next()
                }
            }
        }
        Rectangle {
            x: 16; y: parent.height - 17
            width: parent.width - 32; height: 2; radius: 1
            color: Qt.rgba(Theme.textMain.r, Theme.textMain.g, Theme.textMain.b, 0.12)
            visible: S.WidgetMedia.available && S.WidgetMedia.length > 0
            Rectangle {
                height: parent.height; radius: 1
                width: parent.width * Math.max(0, Math.min(1, S.WidgetMedia.position / Math.max(1, S.WidgetMedia.length)))
                color: Theme.accentCyan
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
        Behavior on x { enabled: root.initialized && !root.settling; NumberAnimation { id: prioritiesX; duration: root.moveDuration; easing.type: Easing.OutQuint } }
        Behavior on y { enabled: root.initialized && !root.settling; NumberAnimation { id: prioritiesY; duration: root.moveDuration; easing.type: Easing.OutQuint } }

        C.Label { x: 18; y: 17; text: "MAKE ROOM FOR"; font.pixelSize: 9; font.letterSpacing: 2; color: prioritiesCard.secondaryText; font.weight: Font.DemiBold }
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
                        width: 17; height: 17; radius: 5
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
        Behavior on x { enabled: root.initialized && !root.settling; NumberAnimation { id: deadlineX; duration: root.moveDuration; easing.type: Easing.OutQuint } }
        Behavior on y { enabled: root.initialized && !root.settling; NumberAnimation { id: deadlineY; duration: root.moveDuration; easing.type: Easing.OutQuint } }

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
            font.pixelSize: 9; color: deadlineCard.secondaryText
        }
        Accessible.role: Accessible.Button
        Accessible.name: (deadlineCard.deadline.title || "Personal deadline") + ", " + S.Widgets.deadlineText + ". Edit deadline"
        Accessible.onPressAction: root.edit()
    }
}
