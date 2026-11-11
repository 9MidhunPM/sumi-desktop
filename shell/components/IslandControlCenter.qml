pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Widgets
import "../config"
import "../services" as S

// The same two-column control grammar as the HTML reference. Service ownership
// stays with the shell; this surface only presents state and dispatches actions.
Item {
    id: root
    required property var app
    property bool active: true
    property double now: Date.now()
    property var spectrumSamples: []
    readonly property bool compact: width < 420
    readonly property real gap: Metrics.space3
    readonly property real major: (width - gap) / 2
    readonly property real topHeight: 196
    readonly property real lowerHeight: compact ? 146 : 140
    implicitHeight: modules.implicitHeight
    signal settingsRequested(string section)
    signal captureRequested(bool annotate)
    signal recordingRequested()

    component ConnectionRow: Item {
        id: row
        property string iconName: "wifi"
        property string title: ""
        property string detail: ""
        property string destination: ""
        property bool selected: false
        property bool available: true
        signal toggleRequested()
        height: root.compact ? 58 : 53
        Button {
            id: toggle
            anchors { left: parent.left; verticalCenter: parent.verticalCenter }
            width: Metrics.target; height: width
            enabled: row.available
            focusPolicy: Qt.StrongFocus; hoverEnabled: true
            Accessible.name: (row.selected ? "Turn off " : "Turn on ") + row.title
            opacity: enabled ? 1 : .4
            onClicked: row.toggleRequested()
            onPressAndHold: root.settingsRequested(row.destination)
            background: Rectangle {
                radius: width / 2
                color: row.selected ? "#3478f6" : toggle.hovered ? IslandStyle.hover : "#34343b"
                border.width: toggle.visualFocus ? 2 : 0; border.color: IslandStyle.text
                Behavior on color { ColorAnimation { duration: IslandStyle.transition } }
            }
            contentItem: Icon { name: row.iconName; size: 19; color: "#ffffff" }
        }
        Button {
            id: details
            anchors { left: toggle.right; right: parent.right; top: parent.top; bottom: parent.bottom; leftMargin: root.compact ? 7 : 11 }
            focusPolicy: Qt.StrongFocus; hoverEnabled: true
            Accessible.name: row.title + ", " + row.detail + ", open settings"
            onClicked: root.settingsRequested(row.destination)
            background: Rectangle { color: details.hovered ? IslandStyle.hover : "transparent"; radius: IslandStyle.smallRadius; border.width: details.visualFocus ? 2 : 0; border.color: IslandStyle.text }
            contentItem: Item {
                Column {
                    anchors { left: parent.left; right: arrow.left; rightMargin: 4; verticalCenter: parent.verticalCenter }
                    spacing: 3
                    Label { width: parent.width; text: row.title; font.pixelSize: root.compact ? 12 : 13; font.weight: Font.DemiBold; color: IslandStyle.text; elide: Text.ElideRight }
                    Label { width: parent.width; text: row.detail; font.pixelSize: root.compact ? 10 : 11; color: IslandStyle.secondary; elide: Text.ElideRight }
                }
                Icon { id: arrow; anchors { right: parent.right; verticalCenter: parent.verticalCenter } name: "chevron-right"; size: 12; color: IslandStyle.secondary }
            }
        }
    }
    component MediaButton: Button {
        id: mediaButton
        property string iconName: "play"
        width: Metrics.target; height: Metrics.target
        hoverEnabled: true; focusPolicy: Qt.StrongFocus
        opacity: enabled ? 1 : .4
        background: Rectangle { color: mediaButton.down || mediaButton.hovered ? IslandStyle.hover : "transparent"; radius: 12; border.width: mediaButton.visualFocus ? 2 : 0; border.color: IslandStyle.text }
        contentItem: Icon { name: mediaButton.iconName; size: 22; color: IslandStyle.text }
    }

    GridLayout {
        objectName: "islandControlModules"
        id: modules
        width: parent.width
        columns: root.compact ? 1 : 2
        columnSpacing: root.gap
        rowSpacing: root.gap
        uniformCellWidths: true
    Rectangle {
        id: connectivity
        objectName: "islandConnectivityModule"
        Layout.row: 0; Layout.column: 0
        Layout.fillWidth: true; Layout.preferredHeight: root.topHeight
        radius: IslandStyle.moduleRadius; color: IslandStyle.raised
        Column {
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Metrics.space3 }
            spacing: 1
            ConnectionRow { width: parent.width; title: "Wi-Fi"; detail: !S.Network.wifiAvailable ? "Unavailable" : S.Network.wifiEnabled ? S.Network.name : "Off"; iconName: "wifi"; destination: "wifi"; selected: S.Network.wifiEnabled; available: S.Network.wifiAvailable; onToggleRequested: S.Network.toggleWifi() }
            ConnectionRow { width: parent.width; title: "Bluetooth"; detail: !S.Bluetooth.available ? "Unavailable" : !S.Bluetooth.enabled ? "Off" : S.Bluetooth.connectedCount ? S.Bluetooth.connectedCount + " connected" : "On"; iconName: "bluetooth"; destination: "bluetooth"; selected: S.Bluetooth.enabled; available: S.Bluetooth.available; onToggleRequested: S.Bluetooth.toggle() }
        }
        IslandPreviewButton {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 7 }
            implicitHeight: Metrics.target; font.pixelSize: root.compact ? 9 : 10
            text: "Connected devices ›"; iconName: "volume"; iconSize: 13; quiet: true
            tooltip: "Choose sound input and output devices"
            onClicked: root.settingsRequested("audio")
        }
    }
    ColumnLayout {
        Layout.row: root.compact ? 1 : 0; Layout.column: root.compact ? 0 : 1
        Layout.fillWidth: true; spacing: root.gap
        RowLayout {
        Layout.fillWidth: true; spacing: root.gap
    IslandControlTile {
        objectName: "islandDndTile"
        Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.preferredHeight: 96
        iconName: "bell-off"; title: "Do Not Disturb"; subtitle: S.Notifications.dnd ? "On" : "Off"
        selected: S.Notifications.dnd; activeColor: "#32303b"; glyphColor: selected ? "#cfb5ff" : IslandStyle.text
        onClicked: S.Notifications.toggleDnd()
    }
    IslandControlTile {
        objectName: "islandNightTile"
        Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.preferredHeight: 96
        iconName: "moon"; title: "Night light"; subtitle: S.NightLight.active ? "On" : "Off"
        selected: S.NightLight.active; activeColor: "#3b3227"; glyphColor: selected ? "#f3b575" : IslandStyle.text
        enabled: S.NightLight.available && !S.NightLight.busy
        onClicked: S.NightLight.toggle()
    }
    }
    Rectangle {
        Layout.fillWidth: true; Layout.preferredHeight: 88
        radius: IslandStyle.moduleRadius; color: IslandStyle.raised
        RowLayout {
            anchors { top: parent.top; left: parent.left; right: parent.right; margins: 12; topMargin: 4 }
            height: 40; spacing: 8
            Icon { name: S.Battery.charging ? "battery-charging" : "battery"; size: 18; color: IslandStyle.text }
            Label { text: S.Battery.available ? Math.round(S.Battery.percent) + "%" : "AC power"; font.pixelSize: 11; color: IslandStyle.text }
            Item { Layout.fillWidth: true }
            IslandPreviewButton { implicitWidth: Metrics.target; implicitHeight: Metrics.target; leftPadding: 2; rightPadding: 2; text: "›"; quiet: true; tooltip: "Battery and session controls"; onClicked: root.settingsRequested("power") }
        }
        IslandPowerProfiles { anchors { bottom: parent.bottom; left: parent.left; right: parent.right; margins: 4 } height: 34 }
    }
    }
    Rectangle {
        id: media
        objectName: "islandControlsMusicModule"
        Layout.row: root.compact ? 2 : 1; Layout.column: 0
        Layout.fillWidth: true; Layout.preferredHeight: root.lowerHeight
        radius: IslandStyle.moduleRadius; color: IslandStyle.raised
        Button {
            id: mediaLink
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Metrics.space3 }
            height: 52; hoverEnabled: true; focusPolicy: Qt.StrongFocus
            Accessible.name: "Open now playing, " + (S.IslandMedia.available ? S.IslandMedia.title : "No music playing")
            onClicked: root.settingsRequested("media")
            background: Rectangle { color: mediaLink.hovered ? IslandStyle.hover : "transparent"; radius: IslandStyle.controlRadius; border.width: mediaLink.visualFocus ? 2 : 0; border.color: IslandStyle.text }
            contentItem: Item {
                ClippingRectangle {
                    id: artwork
                    anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                    width: root.compact ? 34 : 42; height: width; radius: width * .22; color: "#34343b"
                    Icon { anchors.centerIn: parent; name: "music"; size: 20; color: IslandStyle.secondary; visible: tileArtwork.status !== Image.Ready }
                    ArtworkImage { id: tileArtwork; anchors.fill: parent; artworkUrl: S.IslandMedia.artUrl; active: root.active && S.IslandMedia.available; fillMode: Image.PreserveAspectCrop; sourceSize: Qt.size(84,84); visible: status === Image.Ready }
                }
                Column {
                    anchors { left: artwork.right; right: waveform.visible ? waveform.left : parent.right; leftMargin: root.compact ? 7 : 10; rightMargin: waveform.visible ? 8 : 0; verticalCenter: parent.verticalCenter }
                    spacing: 4
                    Label { objectName: "islandControlsTrackTitle"; width: parent.width; text: S.IslandMedia.available ? S.IslandMedia.title : "Not playing"; elide: Text.ElideRight; font.pixelSize: root.compact ? 11 : 13; font.weight: Font.DemiBold; color: IslandStyle.text }
                    Label { width: parent.width; text: S.IslandMedia.artist || "Your soundtrack"; elide: Text.ElideRight; font.pixelSize: root.compact ? 10 : 11; color: IslandStyle.secondary }
                }
                IslandWaveform { id: waveform; objectName: "islandControlsWaveform"; anchors { right: parent.right; verticalCenter: parent.verticalCenter } width: 38; height: 23; barCount: 9; visible: !root.compact && S.IslandMedia.available; samples: root.spectrumSamples; active: root.active && S.IslandMedia.playing; tint: "#dfb0e1" }
            }
        }
        Row {
            anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 13 }
            spacing: root.compact ? 2 : 12
            MediaButton { iconName: "chevron-down"; rotation: 90; Accessible.name: "Previous track"; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canGoPrevious; onClicked: S.IslandMedia.previous() }
            MediaButton { objectName: "islandControlCenterPlay"; iconName: S.IslandMedia.playing ? "pause" : "play"; Accessible.name: S.IslandMedia.playing ? "Pause" : "Play"; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canTogglePlaying; onClicked: S.IslandMedia.toggle() }
            MediaButton { iconName: "chevron-down"; rotation: -90; Accessible.name: "Next track"; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canGoNext; onClicked: S.IslandMedia.next() }
        }
    }
    Rectangle {
        Layout.row: root.compact ? 3 : 1; Layout.column: root.compact ? 0 : 1
        Layout.fillWidth: true; Layout.preferredHeight: root.lowerHeight
        radius: IslandStyle.moduleRadius; color: IslandStyle.raised
        IslandLevelSlider {
            objectName: "islandDashboardBrightness"
            x: 14; y: 12; width: parent.width - 28; height: 54
            horizontalLayout: true; label: "Brightness"; iconName: "sun"; from: .01
            value: S.Brightness.percent / 100; enabled: S.Brightness.ready
            onMoved: S.Brightness.setPercent(value * 100)
        }
        IslandLevelSlider {
            objectName: "islandDashboardVolume"
            x: 14; y: 76; width: parent.width - 28; height: 54
            horizontalLayout: true; label: "Volume"; iconName: S.Audio.muted ? "volume-x" : "volume"
            toggleable: true; muted: S.Audio.muted; onToggleRequested: S.Audio.toggleMute()
            value: S.Audio.volume; enabled: S.Audio.hasOutput
            onMoved: S.Audio.setVolume(value)
        }
    }
    }
}
