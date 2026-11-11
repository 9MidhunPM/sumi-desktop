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
    readonly property color clockAccent: darkClock ? "#633142" : Theme.accentCyan
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
            x: 0; y: root.compact ? 0 : 6
            width: parent.width
            text: Qt.formatDateTime(S.Clock.date, "dddd")
            color: root.clockText
            font.pixelSize: root.compact ? 16 : 18
            font.letterSpacing: 0.2
            font.weight: Font.DemiBold
            style: root.darkClock ? Text.Normal : Text.Outline; styleColor: "#60000000"
        }
        Row {
            x: -7.5; y: root.compact ? 24 : 33
            spacing: 18
            Row {
                spacing: -6
                Repeater {
                    model: [S.Clock.hour, ":", S.Clock.minute]
                    C.Label {
                        required property string modelData
                        required property int index
                        objectName: "desktopClockDigit" + index
                        text: modelData
                        color: index === 1 ? root.clockAccent : root.clockText
                        font.family: Theme.fontMono
                        font.pixelSize: index === 1 ? (root.compact ? 80 : 110) : (root.compact ? 93 : 129)
                        font.weight: index === 1 ? Font.Light : Font.Light
                        font.letterSpacing: index === 1 ? 0 : root.compact ? -3.2 : -4.5
                        style: root.darkClock ? Text.Normal : Text.Outline; styleColor: "#50000000"
                        Accessible.ignored: true
                    }
                }
            }
            C.Label {
                anchors.bottom: parent.bottom
                anchors.bottomMargin: root.compact ? 18 : 25
                text: S.Clock.period
                color: root.clockText
                font.family: Theme.fontMono
                font.pixelSize: root.compact ? 24 : 33
                font.weight: Font.Bold
                style: root.darkClock ? Text.Normal : Text.Outline; styleColor: "#60000000"
            }
        }
        C.Label {
            x: 0; y: root.compact ? 136.5 : 187.5
            width: parent.width
            text: Qt.formatDateTime(S.Clock.date, "d MMMM yyyy")
            color: root.clockText
            font.pixelSize: root.compact ? 18 : 21
            font.letterSpacing: 1.5
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
            objectName: "desktopSpotifyAlbum"
            x: 18; y: 18
            width: root.compact ? 112 : 144; height: width
            radius: IslandStyle.radius
            color: Theme.glassInset
            clip: true
            C.Icon {
                objectName: "desktopSpotifyArtworkFallback"
                anchors.centerIn: parent; name: "music"; size: root.compact ? 38 : 48
                color: musicCard.mainText
                visible: artwork.status !== Image.Ready
            }
            C.ArtworkImage {
                id: artwork
                objectName: "desktopSpotifyArtwork"
                anchors.fill: parent
                artworkUrl: root.artworkSource
                active: root.eligible && !root.idle && WidgetLayout.enabled(root.flags, "spotify")
                sourceSize: Qt.size(288, 288)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: true
                visible: status === Image.Ready
            }
            Rectangle {
                anchors.fill: parent; radius: parent.radius
                color: "transparent"; border.width: 1; border.color: Theme.glassRim
            }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: S.WidgetMedia.openSpotify() }
            Accessible.role: Accessible.Button
            Accessible.name: "Open Spotify"
            Accessible.onPressAction: S.WidgetMedia.openSpotify()
        }
        Item {
            id: musicInfo
            x: album.x + album.width + 20; y: 18
            width: parent.width - x - 20
            height: root.compact ? 126 : 154
            Row {
                spacing: 7
                Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 5; height: 5; radius: 3; color: S.WidgetMedia.playing ? Theme.accentCyan : musicCard.secondaryText }
                C.Label { text: "Spotify"; font.pixelSize: 11; font.letterSpacing: 0; color: musicCard.secondaryText; font.weight: Font.DemiBold }
            }
            C.Label {
                objectName: "desktopSpotifyTitle"
                y: root.compact ? 19 : 23; width: parent.width
                text: S.WidgetMedia.available ? S.WidgetMedia.title : "A little music?"
                color: musicCard.mainText
                font.pixelSize: root.compact ? 17 : 21
                font.weight: Font.DemiBold
                wrapMode: Text.Wrap
                maximumLineCount: 2
                height: root.compact ? 40 : 50
            }
            C.Label {
                objectName: "desktopSpotifyArtist"
                y: root.compact ? 62 : 77; width: parent.width
                text: S.WidgetMedia.available ? S.WidgetMedia.artist : "Open Spotify to begin"
                font.pixelSize: root.compact ? 12 : 13
                color: musicCard.secondaryText
            }
            Row {
                y: root.compact ? 83 : 103
                spacing: 14
                C.ActionButton {
                    objectName: "desktopSpotifyPrevious"
                    text: "‹"; font.pixelSize: 30; quiet: true
                    width: 36; height: root.compact ? 40 : 46; padding: 0
                    textColor: musicCard.mainText
                    tooltip: "Previous Spotify track"
                    enabled: !!S.WidgetMedia.player && S.WidgetMedia.player.canGoPrevious
                    onClicked: S.WidgetMedia.previous()
                }
                C.ActionButton {
                    id: playButton
                    objectName: "desktopSpotifyPlay"
                    iconName: S.WidgetMedia.playing ? "pause" : "play"; iconSize: 20
                    width: root.compact ? 40 : 46; height: width; padding: 0
                    textColor: musicCard.mainText
                    background: C.Surface {
                        radius: height / 2
                        color: Theme.glassFill
                        border.width: playButton.visualFocus ? 2 : 1
                        border.color: playButton.visualFocus ? Theme.accentBlue : Theme.glassRim
                        opacity: playButton.down ? 0.75 : 1
                    }
                    tooltip: S.WidgetMedia.available ? (S.WidgetMedia.playing ? "Pause Spotify" : "Play Spotify") : "Open Spotify"
                    enabled: !S.WidgetMedia.available || (!!S.WidgetMedia.player && S.WidgetMedia.player.canTogglePlaying)
                    onClicked: { if (S.WidgetMedia.available) S.WidgetMedia.toggle(); else S.WidgetMedia.openSpotify(); }
                }
                C.ActionButton {
                    objectName: "desktopSpotifyNext"
                    text: "›"; font.pixelSize: 30; quiet: true
                    width: 36; height: root.compact ? 40 : 46; padding: 0
                    textColor: musicCard.mainText
                    tooltip: "Next Spotify track"
                    enabled: !!S.WidgetMedia.player && S.WidgetMedia.player.canGoNext
                    onClicked: S.WidgetMedia.next()
                }
            }
        }
        Rectangle {
            objectName: "desktopSpotifyProgress"
            x: 18; y: parent.height - 27
            width: parent.width - 36; height: 3; radius: 1.5
            color: Theme.glassInset
            visible: S.WidgetMedia.available && S.WidgetMedia.length > 0
            Rectangle {
                objectName: "desktopSpotifyProgressFill"
                height: parent.height; radius: 1.5
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
