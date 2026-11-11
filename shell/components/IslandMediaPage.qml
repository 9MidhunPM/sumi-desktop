pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell.Widgets
import "../config"
import "../services" as S

ColumnLayout {
    id: root
    property bool active: false
    property real mediaPosition: 0
    property bool sourcesExpanded: false
    property bool showExtras: true
    property alias primaryControl: transportPlay
    property var samples: []
    readonly property real trackLength: S.IslandMedia.player && S.IslandMedia.player.lengthSupported ? Math.max(0, S.IslandMedia.player.length) : 0
    readonly property var sources: S.Media.players.filter(player => S.IslandMedia.meaningful(player))
    signal detailsRequested()
    spacing: 0
    function time(seconds) {
        if (!isFinite(seconds) || seconds < 0) return "--:--";
        const value = Math.floor(seconds);
        return Math.floor(value/60) + ":" + String(value%60).padStart(2,"0");
    }
    Rectangle {
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        implicitHeight: content.implicitHeight + (root.showExtras ? 32 : 0)
        Layout.minimumHeight: implicitHeight
        radius: 28
        color: "transparent"
        ColumnLayout {
            id: content
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: root.showExtras ? 16 : 0 }
            spacing: root.showExtras ? 11 : 4
            RowLayout {
                Layout.fillWidth: true; Layout.minimumWidth: 0
                spacing: Metrics.space3
                ClippingRectangle {
                    Layout.preferredWidth: root.showExtras ? 104 : 64
                    Layout.preferredHeight: root.showExtras ? 104 : 64
                    radius: 13; color: "#242429"
                    Icon { anchors.centerIn: parent; name: "music"; size: 28; color: "#b4b8c7"; visible: art.status !== Image.Ready }
                    ArtworkImage { id: art; objectName: "islandNowPlayingArtwork"; anchors.fill: parent; artworkUrl: S.IslandMedia.artUrl; active: root.active && S.IslandMedia.available; fillMode: Image.PreserveAspectCrop; sourceSize: Qt.size(216,216); visible: status === Image.Ready }
                }
                ColumnLayout {
                    Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 4
                    Label { objectName: "islandDashboardTrackTitle"; Layout.fillWidth: true; Layout.minimumWidth: 0; text: S.IslandMedia.available ? S.IslandMedia.title : "Nothing playing"; font.pixelSize: 16; font.weight: Font.DemiBold; color: IslandStyle.text; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
                    Label { Layout.fillWidth: true; Layout.minimumWidth: 0; text: S.IslandMedia.artist || (S.IslandMedia.available ? S.IslandMedia.player.identity || "Media player" : "Your next soundtrack starts here"); font.pixelSize: 12; color: IslandStyle.secondary; maximumLineCount: 1; elide: Text.ElideRight }
                }
                IslandWaveform { objectName: "islandMediaWaveform"; Layout.preferredWidth: 46; Layout.preferredHeight: 24; barCount: 10; samples: root.samples; active: root.active && S.IslandMedia.playing; visible: S.IslandMedia.available }
            }
            ColumnLayout {
                Layout.fillWidth: true; Layout.minimumWidth: 0
                spacing: 0
                visible: S.IslandMedia.available
                Layout.minimumHeight: root.showExtras ? 40 : 32
                QuickSlider {
                    id: seek
                    objectName: "islandNowPlayingSeek"
                    Layout.fillWidth: true; Layout.minimumWidth: 0
                    implicitHeight: root.showExtras ? 24 : 18
                    label: "Track position"
                    to: Math.max(1, root.trackLength)
                    value: root.mediaPosition
                    stepSize: 1
                    enabled: !!S.IslandMedia.player && S.IslandMedia.player.canSeek && root.trackLength > 0
                    onMoved: S.IslandMedia.seek(value)
                    background: Rectangle { y: (seek.height-height)/2; width: seek.width; height: 4; radius: 2; color: IslandStyle.line; Rectangle { width: seek.visualPosition*parent.width; height: parent.height; radius: 2; color: IslandStyle.text } }
                    handle: Rectangle { x: seek.visualPosition*(seek.width-width); y: (seek.height-height)/2; width: 9; height: 9; radius: 5; color: "white"; visible: seek.visualFocus || seek.pressed }
                }
                RowLayout {
                    Layout.fillWidth: true; Layout.minimumWidth: 0
                    Layout.minimumHeight: 14
                    Layout.preferredHeight: 14
                    Label { objectName: "islandNowPlayingPosition"; text: S.IslandMedia.available ? root.time(root.mediaPosition) : "--:--"; font.pixelSize: 10; color: IslandStyle.secondary }
                    Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }
                    Label { objectName: "islandNowPlayingDuration"; text: root.trackLength > 0 ? root.time(root.trackLength) : "--:--"; font.pixelSize: 10; color: IslandStyle.secondary }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                visible: S.IslandMedia.available
                spacing: 18
                Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }
                IslandPreviewButton { iconName: "chevron-down"; rotation: 90; iconSize: 27; tooltip: "Previous track"; quiet: true; implicitWidth: 40; implicitHeight: 40; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canGoPrevious; onClicked: S.IslandMedia.previous() }
                IslandPreviewButton { id: transportPlay; objectName: "islandDashboardPlay"; iconName: S.IslandMedia.playing ? "pause" : "play"; iconSize: 27; tooltip: S.IslandMedia.playing ? "Pause" : "Play"; quiet: true; implicitWidth: 44; implicitHeight: 40; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canTogglePlaying; onClicked: S.IslandMedia.toggle() }
                IslandPreviewButton { iconName: "chevron-down"; rotation: -90; iconSize: 27; tooltip: "Next track"; quiet: true; implicitWidth: 40; implicitHeight: 40; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canGoNext; onClicked: S.IslandMedia.next() }
                Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }
            }
            RowLayout {
                Layout.fillWidth: true; Layout.minimumWidth: 0
                spacing: Metrics.space2
                visible: root.showExtras
                IslandPreviewButton { objectName: "islandNowPlayingSources"; Layout.fillWidth: true; Layout.minimumWidth: 0; iconName: "music"; iconSize: 14; text: (S.IslandMedia.player ? S.IslandMedia.player.identity || "Media" : "Sources") + "  ⌄"; font.pixelSize: 11; implicitHeight: 31; enabled: root.sources.length > 0; onClicked: root.sourcesExpanded = !root.sourcesExpanded }
                IslandPreviewButton { Layout.fillWidth: true; Layout.minimumWidth: 0; iconName: "volume"; iconSize: 14; text: S.Audio.outputName || "Sound output"; font.pixelSize: 11; implicitHeight: 31; quiet: true; tooltip: "Choose sound output"; onClicked: root.detailsRequested() }
            }
            Flow {
                Layout.fillWidth: true; Layout.minimumWidth: 0
                visible: root.showExtras && root.sourcesExpanded && root.sources.length > 0
                spacing: Metrics.space2
                Repeater {
                    model: root.sources
                    IslandPreviewButton { required property var modelData; width: Math.min(implicitWidth, content.width); text: modelData.identity || modelData.dbusName; selected: S.IslandMedia.player === modelData; implicitHeight: 30; font.pixelSize: 11; onClicked: { S.IslandMedia.select(modelData); root.sourcesExpanded = false; } }
                }
            }
        }
    }
}
