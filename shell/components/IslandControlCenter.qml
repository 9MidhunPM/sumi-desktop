pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Widgets
import "../services" as S

Item {
    id: root
    required property var app
    property bool active: true
    property double now: Date.now()
    readonly property bool wide: width >= 520
    readonly property real gap: 12
    readonly property real major: wide ? (width - gap * 2) / 3 : (width - gap) / 2
    readonly property real topHeight: wide ? Math.min(192, major) : 172
    readonly property real sliderTop: wide ? 0 : topHeight + gap
    readonly property real actionsTop: wide ? topHeight + gap : sliderTop + 172 + gap
    readonly property real footerTop: actionsTop + (wide ? 82 : 172) + gap
    implicitHeight: footerTop + (wide ? 134 : 206)
    signal settingsRequested(string section)
    signal captureRequested(bool annotate)
    signal recordingRequested()

    function remaining() {
        const seconds = Math.max(0, Math.ceil((app.focusRunning ? app.focusDeadline - now : app.focusRemaining) / 1000));
        return Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0");
    }
    component CircleControl: Button {
        property string iconName: "wifi"
        property string title: ""
        property string accessibleTitle: title
        property bool selected: false
        property color activeColor: "#087df1"
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: accessibleTitle
        opacity: enabled ? 1 : .4
        background: Item {}
        contentItem: Item {
            Rectangle {
                anchors { top: parent.top; horizontalCenter: parent.horizontalCenter }
                width: Math.min(46, parent.width - 6)
                height: width
                radius: width / 2
                color: parent.parent.selected ? parent.parent.activeColor : parent.parent.down ? "#62636c" : "#494a53"
                border.width: parent.parent.visualFocus ? 2 : 0
                border.color: "#ffffff"
                Icon { anchors.centerIn: parent; name: parent.parent.parent.iconName; size: 23; color: "#ffffff" }
            }
            Label { anchors { bottom: parent.bottom; left: parent.left; right: parent.right } text: parent.parent.title; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 10; color: "#ececf1" }
        }
    }
    component MediaButton: Button {
        property string iconName: "play"
        width: 38
        height: 38
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        background: Rectangle { color: parent.down ? "#5b5b66" : parent.hovered ? "#45454f" : "transparent"; radius: 19; border.width: parent.visualFocus ? 2 : 0; border.color: "#ffffff" }
        contentItem: Icon { name: parent.iconName; size: 22; color: "#f8f8fb" }
    }
    component FooterButton: Button {
        property bool selected: false
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        padding: 6
        font.pixelSize: 11
        background: Rectangle { radius: 15; color: parent.selected ? "#f6f6f8" : parent.down ? "#55555e" : "#35363e"; border.width: parent.visualFocus ? 2 : 0; border.color: "#ffffff" }
        contentItem: Label { text: parent.text; color: parent.selected ? "#222229" : "#ededf2"; font: parent.font; horizontalAlignment: Text.AlignHCenter }
    }

    Rectangle {
        id: connectivity
        objectName: "islandConnectivityModule"
        width: root.major
        height: root.topHeight
        radius: 26
        color: "#24252b"
        Grid {
            anchors.fill: parent
            anchors.margins: 11
            columns: 2
            spacing: 6
            CircleControl { width: (connectivity.width - 28) / 2; height: (connectivity.height - 28) / 2; title: "Wi-Fi"; iconName: "wifi"; selected: S.Network.wifiEnabled; enabled: S.Network.wifiAvailable; onClicked: S.Network.toggleWifi(); onPressAndHold: root.settingsRequested("wifi") }
            CircleControl { width: (connectivity.width - 28) / 2; height: (connectivity.height - 28) / 2; title: "Bluetooth"; iconName: "bluetooth"; selected: S.Bluetooth.enabled; enabled: S.Bluetooth.available; onClicked: S.Bluetooth.toggle(); onPressAndHold: root.settingsRequested("bluetooth") }
            CircleControl { width: (connectivity.width - 28) / 2; height: (connectivity.height - 28) / 2; title: "DND"; accessibleTitle: "Do Not Disturb"; iconName: "bell-off"; selected: S.Notifications.dnd; activeColor: "#7656d6"; onClicked: S.Notifications.toggleDnd() }
            CircleControl { width: (connectivity.width - 28) / 2; height: (connectivity.height - 28) / 2; title: "Night light"; iconName: "moon"; selected: S.NightLight.active; activeColor: "#b47b35"; enabled: S.NightLight.available && !S.NightLight.busy; onClicked: S.NightLight.toggle() }
        }
    }
    Rectangle {
        id: media
        x: root.major + root.gap
        width: root.major
        height: root.topHeight
        radius: 26
        color: "#24252b"
        ClippingRectangle {
            x: parent.width - 51; y: 12; width: 36; height: 36; radius: 9; color: "#3b3c44"
            Icon { anchors.centerIn: parent; name: "music"; size: 20; color: "#c4c5cf"; visible: tileArtwork.status !== Image.Ready }
            ArtworkImage { id: tileArtwork; anchors.fill: parent; artworkUrl: S.IslandMedia.artUrl; active: root.active && S.IslandMedia.available; fillMode: Image.PreserveAspectCrop; sourceSize: Qt.size(72,72); visible: status === Image.Ready }
        }
        Icon { x: 15; y: 17; name: "music"; size: 19; color: "#a9abb7" }
        Label { x: 15; y: 47; width: parent.width - 30; height: 42; text: S.IslandMedia.title; wrapMode: Text.Wrap; maximumLineCount: 2; font.pixelSize: root.wide ? 15 : 13; font.weight: Font.DemiBold; color: "#f8f8fb" }
        Label { x: 15; y: 92; width: parent.width - 30; text: S.IslandMedia.artist || "Your soundtrack"; font.pixelSize: 11; color: "#aeb0bc" }
        Row {
            anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 10 }
            spacing: root.wide ? 8 : 0
            MediaButton { iconName: "chevron-down"; rotation: 90; Accessible.name: "Previous track"; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canGoPrevious; onClicked: S.IslandMedia.previous() }
            MediaButton { objectName: "islandControlCenterPlay"; iconName: S.IslandMedia.playing ? "pause" : "play"; Accessible.name: S.IslandMedia.playing ? "Pause" : "Play"; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canTogglePlaying; onClicked: S.IslandMedia.toggle() }
            MediaButton { iconName: "chevron-down"; rotation: -90; Accessible.name: "Next track"; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canGoNext; onClicked: S.IslandMedia.next() }
        }
    }
    IslandLevelSlider {
        objectName: "islandDashboardBrightness"
        x: root.wide ? (root.major + root.gap) * 2 : 0
        y: root.sliderTop
        width: root.wide ? (root.major - root.gap) / 2 : root.major
        height: root.wide ? root.topHeight : 172
        label: "Display brightness"
        iconName: "sun"
        from: 0.01
        value: S.Brightness.percent / 100
        enabled: S.Brightness.ready
        onMoved: S.Brightness.setPercent(value * 100)
    }
    IslandLevelSlider {
        objectName: "islandDashboardVolume"
        x: root.wide ? root.width - width : root.major + root.gap
        y: root.sliderTop
        width: root.wide ? (root.major - root.gap) / 2 : root.major
        height: root.wide ? root.topHeight : 172
        label: "Output volume"
        toggleable: true
        muted: S.Audio.muted
        onToggleRequested: S.Audio.toggleMute()
        iconName: S.Audio.muted ? "volume-x" : "volume"
        value: S.Audio.volume
        enabled: S.Audio.hasOutput
        onMoved: S.Audio.setVolume(value)
    }
    IslandControlTile {
        id: focusTile
        objectName: "islandControlFocus"
        x: 0; y: root.actionsTop
        width: root.wide ? root.major : root.width
        height: 82
        title: "Focus"
        subtitle: root.app.focusRunning ? root.remaining() + " remaining" : "Start a focused moment"
        iconName: "moon"
        selected: root.app.focusRunning
        activeColor: "#534179"
        glyphColor: root.app.focusRunning ? "#d0b6ff" : "#b799f3"
        onClicked: { if (root.app.focusRunning) root.app.focusPause(); else root.app.focusStart(); }
        onPressAndHold: root.app.focusReset(25)
    }
    IslandControlTile {
        id: micTile
        objectName: "islandControlMic"
        x: root.wide ? root.major + root.gap : 0
        y: root.actionsTop + (root.wide ? 0 : 94)
        width: root.wide ? (root.major - root.gap) / 2 : (root.width - root.gap * 2) / 3
        height: 78
        iconName: S.Audio.sourceMuted ? "microphone-off" : "microphone"
        title: S.Audio.sourceMuted ? "Mic off" : "Mic on"
        enabled: S.Audio.hasInput
        onClicked: S.Audio.toggleSourceMute()
        onPressAndHold: root.settingsRequested("audio")
    }
    IslandControlTile {
        id: captureTile
        objectName: "islandControlCapture"
        x: micTile.x + micTile.width + root.gap
        y: micTile.y
        width: micTile.width
        height: 78
        title: "Capture"
        iconName: "camera"
        onClicked: root.captureRequested(false)
        onPressAndHold: root.captureRequested(true)
    }
    IslandControlTile {
        objectName: "islandDashboardRecord"
        x: root.wide ? (root.major + root.gap) * 2 : captureTile.x + captureTile.width + root.gap
        y: micTile.y
        width: root.wide ? root.major : micTile.width
        height: root.wide ? 82 : 78
        title: S.Recording.recording ? "Stop" : "Record"
        subtitle: root.wide ? S.Recording.recording ? "Recording your screen" : "Select a region" : ""
        iconName: S.Recording.recording ? "stop" : "record"
        glyphColor: S.Recording.recording ? "#ff6b73" : "#f8f8fb"
        enabled: S.Recording.ready && !S.Recording.busy
        onClicked: { if (S.Recording.recording) S.Recording.stop(); else root.recordingRequested(); }
    }
    Rectangle {
        x: 0; y: root.footerTop
        width: root.width
        height: 88
        radius: 24
        color: "#202126"
        RowLayout {
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
            spacing: 7
            Icon { name: S.Battery.charging ? "battery-charging" : "battery"; size: 19; color: "#c8c9d2" }
            Label { text: S.Battery.available ? Math.round(S.Battery.percent) + "%" : "AC power"; color: "#f5f5f8"; font.pixelSize: 12; font.weight: Font.DemiBold }
            Label { text: S.Battery.timeLabel; color: "#a8aab6"; font.pixelSize: 11; Layout.fillWidth: true; Layout.minimumWidth: 0; horizontalAlignment: Text.AlignRight }
        }
        IslandPowerProfiles {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 8 }
        }
    }
    Grid {
        x: 0; y: root.footerTop + 98
        width: root.width
        columns: root.wide ? 5 : 2
        spacing: 6
        Repeater {
            model: ["Annotate", "Sound", "Wi-Fi", "Bluetooth", "More settings"]
            FooterButton {
                required property string modelData
                required property int index
                objectName: index === 4 ? "islandControlMore" : "islandControlDetail" + index
                text: modelData
                width: root.wide ? (root.width - 24) / 5 : (root.width - 6) / 2
                height: 30
                onClicked: { if (index === 0) root.captureRequested(true); else root.settingsRequested(["", "audio", "wifi", "bluetooth", ""][index]); }
            }
        }
    }
}
