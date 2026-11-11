pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Widgets
import "../services" as S
import "../config"

Item {
    id: root
    required property var app
    property bool active: true
    property double now: Date.now()
    property var spectrumSamples: []
    readonly property bool wide: width >= 520
    readonly property real gap: 12
    readonly property real major: wide ? (width - gap * 2) / 3 : (width - gap) / 2
    readonly property real topHeight: wide ? Math.min(192, major) : 172
    readonly property real sliderTop: wide ? 0 : topHeight + gap
    readonly property real actionsTop: wide ? topHeight + gap : sliderTop + 172 + gap
    readonly property real footerTop: actionsTop + (wide ? 82 : 176) + gap
    implicitHeight: footerTop + 88
    signal settingsRequested(string section)
    signal captureRequested(bool annotate)
    signal recordingRequested()

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
        width: Metrics.target
        height: Metrics.target
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        background: Rectangle { color: parent.down ? "#5b5b66" : parent.hovered ? "#45454f" : "transparent"; radius: 19; border.width: parent.visualFocus ? 2 : 0; border.color: "#ffffff" }
        contentItem: Icon { name: parent.iconName; size: 22; color: "#f8f8fb" }
    }

    Rectangle {
        id: connectivity
        objectName: "islandConnectivityModule"
        width: root.major
        height: root.topHeight
        radius: IslandStyle.moduleRadius
        color: IslandStyle.raised
        Grid {
            anchors.fill: parent
            anchors.margins: 11
            columns: 2
            spacing: 6
            CircleControl { width: (connectivity.width - 28) / 2; height: (connectivity.height - 28) / 2; objectName: "islandControlWifi"; title: "Wi-Fi"; accessibleTitle: "Open Wi-Fi settings" + (S.Network.wifiAvailable ? "" : ", unavailable"); iconName: "wifi"; selected: S.Network.wifiEnabled; onClicked: root.settingsRequested("wifi") }
            CircleControl { width: (connectivity.width - 28) / 2; height: (connectivity.height - 28) / 2; objectName: "islandControlBluetooth"; title: "Bluetooth"; accessibleTitle: "Open Bluetooth settings" + (S.Bluetooth.available ? "" : ", unavailable"); iconName: "bluetooth"; selected: S.Bluetooth.enabled; onClicked: root.settingsRequested("bluetooth") }
            CircleControl { width: (connectivity.width - 28) / 2; height: (connectivity.height - 28) / 2; objectName: "islandControlDnd"; title: "DND"; accessibleTitle: "Do Not Disturb"; iconName: "bell-off"; selected: S.Notifications.dnd; activeColor: "#7656d6"; onClicked: S.Notifications.toggleDnd() }
            CircleControl { width: (connectivity.width - 28) / 2; height: (connectivity.height - 28) / 2; objectName: "islandControlNight"; title: "Night light"; iconName: "moon"; selected: S.NightLight.active; activeColor: "#b47b35"; enabled: S.NightLight.available && !S.NightLight.busy; onClicked: S.NightLight.toggle() }
        }
    }
    Rectangle {
        id: media
        objectName: "islandControlsMusicModule"
        x: root.major + root.gap
        width: root.major
        height: root.topHeight
        radius: IslandStyle.moduleRadius
        color: IslandStyle.raised
        ClippingRectangle {
            x: parent.width - 51; y: 12; width: 36; height: 36; radius: 9; color: "#3b3c44"
            Icon { anchors.centerIn: parent; name: "music"; size: 20; color: "#c4c5cf"; visible: tileArtwork.status !== Image.Ready }
            ArtworkImage { id: tileArtwork; anchors.fill: parent; artworkUrl: S.IslandMedia.artUrl; active: root.active && S.IslandMedia.available; fillMode: Image.PreserveAspectCrop; sourceSize: Qt.size(72,72); visible: status === Image.Ready }
        }
        Icon { x: 15; y: 17; name: "music"; size: 19; color: "#a9abb7" }
        IslandWaveform { objectName: "islandControlsWaveform"; anchors { right: parent.right; top: parent.top; rightMargin: 54; topMargin: 19 } width: 38; height: 18; visible: media.width >= 175 && S.IslandMedia.available; samples: root.spectrumSamples; active: root.active && S.IslandMedia.playing; tint: "#dfb0e1" }
        Button {
            anchors { left: parent.left; right: parent.right; top: parent.top; bottom: transport.top }
            background: Rectangle { color: "transparent"; radius: IslandStyle.controlRadius; border.width: parent.visualFocus ? 2 : 0; border.color: IslandStyle.text }
            contentItem: Item {}
            Accessible.name: "Open now playing"
            focusPolicy: Qt.StrongFocus
            onClicked: root.settingsRequested("media")
        }
        Label { x: 15; y: 47; width: parent.width - 30; height: 42; text: S.IslandMedia.title || "Not playing"; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; font.pixelSize: root.wide ? 15 : 13; font.weight: Font.DemiBold; color: "#f8f8fb" }
        Label { x: 15; y: 92; width: parent.width - 30; text: S.IslandMedia.artist || "Your soundtrack"; elide: Text.ElideRight; font.pixelSize: 11; color: "#aeb0bc" }
        Row {
            id: transport
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
        id: volume
        objectName: "islandDashboardVolume"
        x: root.wide ? root.width - width : root.major + root.gap
        y: root.sliderTop
        width: root.wide ? (root.major - root.gap) / 2 : root.major
        height: root.wide ? root.topHeight : 172
        label: "Output volume"
        toggleable: false
        muted: S.Audio.muted
        iconName: S.Audio.muted ? "volume-x" : "volume"
        value: S.Audio.volume
        enabled: S.Audio.hasOutput
        onMoved: S.Audio.setVolume(value)
    }
    Button {
        objectName: "islandVolumeMute"
        x: volume.x + Math.max(0, (volume.width - width) / 2)
        y: volume.y + volume.height - height - 8
        width: Math.min(50, volume.width); height: 48
        enabled: S.Audio.hasOutput; focusPolicy: Qt.StrongFocus
        Accessible.name: S.Audio.muted ? "Unmute sound" : "Mute sound"
        onClicked: S.Audio.toggleMute()
        background: Rectangle { color: "transparent"; radius: 20; border.width: parent.visualFocus ? 2 : 0; border.color: IslandStyle.text }
        contentItem: Item {}
    }
    IslandSystemUsage { x: 0; y: root.actionsTop; width: root.wide ? root.major : (root.width - 12)/2; height: 82; metric: "cpu" }
    IslandSystemUsage { x: root.wide ? root.major + 12 : (root.width + 12)/2; y: root.actionsTop; width: root.wide ? root.major : (root.width - 12)/2; height: 82; metric: "memory" }
    IslandSystemUsage { x: root.wide ? (root.major + 12)*2 : 0; y: root.actionsTop + (root.wide ? 0 : 94); width: root.wide ? root.major : root.width; height: 82; metric: "storage" }
    Rectangle {
        objectName: "islandPowerModule"
        x: 0; y: root.footerTop
        width: root.width
        height: 88
        radius: IslandStyle.moduleRadius
        color: IslandStyle.raised
        RowLayout {
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
            spacing: 7
            Icon { name: S.Battery.charging ? "battery-charging" : "battery"; size: 19; color: "#c8c9d2" }
            Label { text: S.Battery.available ? Math.round(S.Battery.percent) + "%" : "AC power"; color: "#f5f5f8"; font.pixelSize: 12; font.weight: Font.DemiBold }
            Label { text: S.Battery.available ? S.Battery.timeLabel : ""; color: "#a8aab6"; font.pixelSize: 11; Layout.fillWidth: true; Layout.minimumWidth: 0; horizontalAlignment: Text.AlignRight }
        }
        IslandPowerProfiles {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 8 }
        }
    }
}
