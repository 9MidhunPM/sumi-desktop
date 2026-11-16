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
    readonly property string wifiStatus: !S.Network.wifiAvailable ? "Unavailable" : !S.Network.wifiEnabled ? "Off"
        : S.Network.connecting ? "Connecting…" : S.Network.connected && S.Network.name ? S.Network.name : "Not connected"
    readonly property string bluetoothStatus: !S.Bluetooth.available ? "Unavailable" : !S.Bluetooth.enabled ? "Off"
        : S.Bluetooth.connectedCount > 0 ? S.Bluetooth.connectedCount + " connected" : "On"
    implicitHeight: footerTop + 88
    signal settingsRequested(string section)
    signal captureRequested(bool annotate)
    signal recordingRequested()

    // One row per connection: a state disc, its name and what it is doing now.
    component ConnectivityRow: Button {
        id: row
        property string iconName: "wifi"
        property string title: ""
        property string status: ""
        property string accessibleTitle: title
        property bool selected: false
        property color activeColor: "#0a84ff"
        padding: 0
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: accessibleTitle + ", " + status
        opacity: enabled ? 1 : .4
        background: Rectangle {
            radius: 12
            color: row.down ? Qt.rgba(1, 1, 1, 0.08) : row.hovered ? Qt.rgba(1, 1, 1, 0.05) : "transparent"
            border.width: row.visualFocus ? 2 : 0; border.color: "#ffffff"
            Behavior on color { ColorAnimation { duration: Motion.control } }
        }
        contentItem: Item {
            Rectangle {
                id: disc
                x: 6; anchors.verticalCenter: parent.verticalCenter
                width: Math.min(30, row.height - 6); height: width; radius: width / 2
                color: row.selected ? row.activeColor : "#3a3a40"
                Behavior on color { ColorAnimation { duration: Motion.reveal / 2 } }
                Icon { anchors.centerIn: parent; name: row.iconName; size: 16; color: "#ffffff" }
            }
            Column {
                anchors { left: disc.right; leftMargin: 10; right: parent.right; rightMargin: 6; verticalCenter: parent.verticalCenter }
                spacing: 1
                Label { width: parent.width; text: row.title; font.pixelSize: 13; font.weight: Font.DemiBold; color: IslandStyle.text; elide: Text.ElideRight }
                Label { width: parent.width; text: row.status; font.pixelSize: 11; color: IslandStyle.secondary; elide: Text.ElideRight }
            }
        }
    }
    // The disc itself switches the radio, as in macOS; the rest of the row opens details.
    component RadioToggle: Button {
        id: toggle
        property Item row: null
        property bool selected: false
        property string label: ""
        x: row ? row.x + 6 : 0
        y: row ? row.y + (row.height - height) / 2 : 0
        width: row ? Math.min(30, row.height - 6) : 30; height: width
        padding: 0
        focusPolicy: Qt.StrongFocus
        Accessible.name: (selected ? "Turn off " : "Turn on ") + label
        background: Rectangle { radius: width / 2; color: toggle.down ? Qt.rgba(1, 1, 1, 0.18) : "transparent"; border.width: toggle.visualFocus ? 2 : 0; border.color: "#ffffff" }
        contentItem: Item {}
    }
    component MediaButton: Button {
        property string iconName: "play"
        property real glyph: 22
        width: Metrics.target
        height: Metrics.target
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        opacity: enabled ? 1 : .35
        background: Rectangle { color: parent.down ? "#5b5b66" : parent.hovered ? "#45454f" : "transparent"; radius: 19; border.width: parent.visualFocus ? 2 : 0; border.color: "#ffffff" }
        contentItem: Icon { name: parent.iconName; size: parent.glyph; color: "#f8f8fb" }
    }

    Rectangle {
        id: connectivity
        objectName: "islandConnectivityModule"
        width: root.major
        height: root.topHeight
        radius: IslandStyle.moduleRadius
        color: IslandStyle.raised
        Column {
            id: connections
            anchors.fill: parent
            anchors.margins: 6
            spacing: 2
            readonly property real rowHeight: (height - spacing * 3) / 4
            ConnectivityRow {
                id: wifiRow
                objectName: "islandControlWifi"
                width: connections.width; height: connections.rowHeight
                title: "Wi-Fi"; status: root.wifiStatus; iconName: S.Network.wifiEnabled ? "wifi" : "wifi-off"
                accessibleTitle: "Open Wi-Fi settings"
                selected: S.Network.wifiEnabled && S.Network.wifiAvailable
                onClicked: root.settingsRequested("wifi")
            }
            ConnectivityRow {
                id: bluetoothRow
                objectName: "islandControlBluetooth"
                width: connections.width; height: connections.rowHeight
                title: "Bluetooth"; status: root.bluetoothStatus; iconName: S.Bluetooth.enabled ? "bluetooth" : "bluetooth-off"
                accessibleTitle: "Open Bluetooth settings"
                selected: S.Bluetooth.enabled
                onClicked: root.settingsRequested("bluetooth")
            }
            ConnectivityRow {
                objectName: "islandControlDnd"
                width: connections.width; height: connections.rowHeight
                title: "Do Not Disturb"; status: S.Notifications.dnd ? "On" : "Off"; iconName: "bell-off"
                accessibleTitle: "Do Not Disturb"
                selected: S.Notifications.dnd; activeColor: "#7656d6"
                onClicked: S.Notifications.toggleDnd()
            }
            ConnectivityRow {
                objectName: "islandControlNight"
                width: connections.width; height: connections.rowHeight
                title: "Night light"; iconName: "moon"
                status: !S.NightLight.available ? "Unavailable" : S.NightLight.busy ? "Updating…" : S.NightLight.active ? "On" : "Off"
                selected: S.NightLight.active; activeColor: "#c27c2e"
                enabled: S.NightLight.available && !S.NightLight.busy
                onClicked: S.NightLight.toggle()
            }
        }
        RadioToggle {
            objectName: "islandControlWifiToggle"
            row: wifiRow; x: connections.x + wifiRow.x + 6; y: connections.y + wifiRow.y + (wifiRow.height - height) / 2
            label: "Wi-Fi"; selected: S.Network.wifiEnabled
            enabled: S.Network.wifiAvailable
            onClicked: S.Network.toggleWifi()
        }
        RadioToggle {
            objectName: "islandControlBluetoothToggle"
            row: bluetoothRow; x: connections.x + bluetoothRow.x + 6; y: connections.y + bluetoothRow.y + (bluetoothRow.height - height) / 2
            label: "Bluetooth"; selected: S.Bluetooth.enabled
            enabled: S.Bluetooth.available
            onClicked: S.Bluetooth.toggle()
        }
    }
    // Now Playing leads with the artwork and borrows a faint glow of its colour.
    Rectangle {
        id: media
        objectName: "islandControlsMusicModule"
        x: root.major + root.gap
        width: root.major
        height: root.topHeight
        radius: IslandStyle.moduleRadius
        color: IslandStyle.raised
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            visible: S.IslandMedia.available && tileArtwork.status === Image.Ready
            opacity: S.IslandMedia.playing ? 1 : 0.5
            Behavior on opacity { NumberAnimation { duration: Motion.reveal } }
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.rgba(tileAccent.accent.r, tileAccent.accent.g, tileAccent.accent.b, 0.22) }
                GradientStop { position: 0.8; color: Qt.rgba(tileAccent.accent.r, tileAccent.accent.g, tileAccent.accent.b, 0) }
            }
        }
        ArtworkAccent { id: tileAccent; source: tileArtwork.status === Image.Ready ? tileArtwork.source : "" }
        Button {
            anchors { left: parent.left; right: parent.right; top: parent.top; bottom: transport.top }
            background: Rectangle { color: "transparent"; radius: IslandStyle.controlRadius; border.width: parent.visualFocus ? 2 : 0; border.color: IslandStyle.text }
            contentItem: Item {}
            Accessible.name: "Open now playing"
            focusPolicy: Qt.StrongFocus
            onClicked: root.settingsRequested("media")
        }
        ClippingRectangle {
            x: 14; y: 14; width: 46; height: 46; radius: 11; color: "#2c2c31"
            Icon { anchors.centerIn: parent; name: "music"; size: 22; color: "#c4c5cf"; visible: tileArtwork.status !== Image.Ready }
            ArtworkImage { id: tileArtwork; anchors.fill: parent; artworkUrl: S.IslandMedia.artUrl; active: root.active && S.IslandMedia.available; fillMode: Image.PreserveAspectCrop; sourceSize: Qt.size(92, 92); visible: status === Image.Ready }
        }
        IslandWaveform {
            objectName: "islandControlsWaveform"
            anchors { right: parent.right; top: parent.top; rightMargin: 16; topMargin: 29 }
            width: 34; height: 16; barCount: 6; barWidth: 3.2; spacing: 2.4; restHeight: 3.2; restOpacity: 0.5
            visible: media.width >= 175 && S.IslandMedia.available
            samples: root.spectrumSamples; active: root.active && S.IslandMedia.playing; tint: tileAccent.accent
        }
        Label {
            id: trackTitle
            x: 14; y: 70; width: parent.width - 28
            text: S.IslandMedia.available ? S.IslandMedia.title : "Not Playing"
            wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
            font.pixelSize: root.wide ? 14 : 13; font.weight: Font.DemiBold
            color: S.IslandMedia.available ? "#f8f8fb" : IslandStyle.secondary
        }
        Label {
            anchors { top: trackTitle.bottom; topMargin: 2; left: trackTitle.left; right: trackTitle.right }
            visible: text.length > 0
            text: S.IslandMedia.artist || (S.IslandMedia.available && S.IslandMedia.player ? S.IslandMedia.player.identity || "" : "")
            elide: Text.ElideRight; font.pixelSize: 12; color: IslandStyle.secondary
        }
        Row {
            id: transport
            anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 10 }
            spacing: root.wide ? 8 : 0
            MediaButton { iconName: "backward"; glyph: 20; Accessible.name: "Previous track"; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canGoPrevious; onClicked: S.IslandMedia.previous() }
            MediaButton { objectName: "islandControlCenterPlay"; iconName: S.IslandMedia.playing ? "pause-fill" : "play-fill"; glyph: 24; Accessible.name: S.IslandMedia.playing ? "Pause" : "Play"; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canTogglePlaying; onClicked: S.IslandMedia.toggle() }
            MediaButton { iconName: "forward"; glyph: 20; Accessible.name: "Next track"; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canGoNext; onClicked: S.IslandMedia.next() }
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
    IslandSystemUsage { x: 0; y: root.actionsTop; width: root.wide ? root.major : (root.width - 12)/2; height: 82; metric: "cpu"; onActivated: root.settingsRequested("system") }
    IslandSystemUsage { x: root.wide ? root.major + 12 : (root.width + 12)/2; y: root.actionsTop; width: root.wide ? root.major : (root.width - 12)/2; height: 82; metric: "memory"; onActivated: root.settingsRequested("system") }
    IslandSystemUsage { x: root.wide ? (root.major + 12)*2 : 0; y: root.actionsTop + (root.wide ? 0 : 94); width: root.wide ? root.major : root.width; height: 82; metric: "storage"; onActivated: root.settingsRequested("system") }
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
            Icon {
                name: S.Battery.charging ? "battery-charging" : "battery"; size: 19
                color: S.Battery.charging ? "#30d158" : S.Battery.available && S.Battery.percent < 20 ? Theme.accentWarn : "#c8c9d2"
            }
            Label { text: S.Battery.available ? Math.round(S.Battery.percent) + "%" : "AC power"; color: "#f5f5f8"; font.pixelSize: 13; font.weight: Font.DemiBold; font.features: IslandStyle.figures }
            Label {
                text: !S.Battery.available ? "" : S.Battery.charging && S.Battery.timeLabel !== "Charging" ? "Charging · " + S.Battery.timeLabel : S.Battery.timeLabel
                color: "#a8aab6"; font.pixelSize: 11; font.features: IslandStyle.figures
                Layout.fillWidth: true; Layout.minimumWidth: 0; horizontalAlignment: Text.AlignRight; elide: Text.ElideLeft
            }
        }
        IslandPowerProfiles {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 8 }
        }
    }
}
