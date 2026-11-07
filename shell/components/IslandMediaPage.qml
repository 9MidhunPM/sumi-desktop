pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../services" as S

ColumnLayout {
    id: root
    property bool active: false
    property real mediaPosition: 0
    property bool sourcesExpanded: false
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
        implicitHeight: content.implicitHeight + 32
        Layout.minimumHeight: implicitHeight
        radius: 28
        color: "#202126"
        ColumnLayout {
            id: content
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16 }
            spacing: 11
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                implicitWidth: Math.min(184, Math.max(152, root.width * .4))
                implicitHeight: implicitWidth
                radius: 23
                color: "#30323b"
                Icon { anchors.centerIn: parent; name: "music"; size: 48; color: "#b4b8c7"; visible: art.status !== Image.Ready }
                ArtworkImage { id: art; objectName: "islandNowPlayingArtwork"; anchors.fill: parent; artworkUrl: S.IslandMedia.artUrl; active: root.active && S.IslandMedia.available; fillMode: Image.PreserveAspectCrop; sourceSize: Qt.size(384,384); visible: status === Image.Ready }
                // Cover only the outside corners; works with software rendering.
                Canvas {
                    anchors.fill: parent
                    antialiasing: true
                    onWidthChanged: requestPaint()
                    onHeightChanged: requestPaint()
                    onPaint: {
                        const c = getContext("2d"); c.reset();
                        c.fillStyle="#202126"; c.fillRect(0,0,width,height);
                        c.globalCompositeOperation="destination-out";
                        const r=23;
                        c.beginPath(); c.moveTo(r,0); c.lineTo(width-r,0);
                        c.quadraticCurveTo(width,0,width,r); c.lineTo(width,height-r);
                        c.quadraticCurveTo(width,height,width-r,height); c.lineTo(r,height);
                        c.quadraticCurveTo(0,height,0,height-r); c.lineTo(0,r); c.quadraticCurveTo(0,0,r,0); c.closePath(); c.fill();
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true; Layout.minimumWidth: 0
                spacing: 5
                Label { objectName: "islandDashboardTrackTitle"; Layout.fillWidth: true; Layout.minimumWidth: 0; text: S.IslandMedia.available ? S.IslandMedia.title : "Nothing playing"; font.pixelSize: root.width >= 420 ? 22 : 19; font.weight: Font.DemiBold; color: "#fafafd"; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; maximumLineCount: 2 }
                Label { Layout.fillWidth: true; Layout.minimumWidth: 0; text: S.IslandMedia.artist || (S.IslandMedia.available ? S.IslandMedia.player.identity || "Media player" : "Your next soundtrack starts here"); font.pixelSize: 12; color: "#a9adbd"; horizontalAlignment: Text.AlignHCenter; maximumLineCount: 1 }
            }
            ColumnLayout {
                Layout.fillWidth: true; Layout.minimumWidth: 0
                spacing: 0
                Layout.minimumHeight: 40
                QuickSlider {
                    id: seek
                    objectName: "islandNowPlayingSeek"
                    Layout.fillWidth: true; Layout.minimumWidth: 0
                    implicitHeight: 24
                    label: "Track position"
                    to: Math.max(1, root.trackLength)
                    value: root.mediaPosition
                    stepSize: 1
                    enabled: !!S.IslandMedia.player && S.IslandMedia.player.canSeek && root.trackLength > 0
                    onMoved: S.IslandMedia.seek(value)
                    background: Rectangle { y: (seek.height-height)/2; width: seek.width; height: 4; radius: 2; color: "#484b57"; Rectangle { width: seek.visualPosition*parent.width; height: parent.height; radius: 2; color: "#f4f5f9" } }
                    handle: Rectangle { x: seek.visualPosition*(seek.width-width); y: (seek.height-height)/2; width: 9; height: 9; radius: 5; color: "white"; visible: seek.visualFocus || seek.pressed }
                }
                RowLayout {
                    Layout.fillWidth: true; Layout.minimumWidth: 0
                    Layout.minimumHeight: 14
                    Layout.preferredHeight: 14
                    Label { objectName: "islandNowPlayingPosition"; text: S.IslandMedia.available ? root.time(root.mediaPosition) : "--:--"; font.pixelSize: 10; color: "#9fa4b5" }
                    Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }
                    Label { objectName: "islandNowPlayingDuration"; text: root.trackLength > 0 ? root.time(root.trackLength) : "--:--"; font.pixelSize: 10; color: "#9fa4b5" }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 18
                Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }
                IslandPreviewButton { iconName: "chevron-down"; rotation: 90; iconSize: 27; tooltip: "Previous track"; quiet: true; implicitWidth: 44; implicitHeight: 44; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canGoPrevious; onClicked: S.IslandMedia.previous() }
                IslandPreviewButton { objectName: "islandDashboardPlay"; iconName: S.IslandMedia.playing ? "pause" : "play"; iconSize: 27; tooltip: S.IslandMedia.playing ? "Pause" : "Play"; selected: true; implicitWidth: 60; implicitHeight: 52; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canTogglePlaying; onClicked: S.IslandMedia.toggle() }
                IslandPreviewButton { iconName: "chevron-down"; rotation: -90; iconSize: 27; tooltip: "Next track"; quiet: true; implicitWidth: 44; implicitHeight: 44; enabled: !!S.IslandMedia.player && S.IslandMedia.player.canGoNext; onClicked: S.IslandMedia.next() }
                Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }
            }
            RowLayout {
                Layout.fillWidth: true; Layout.minimumWidth: 0
                spacing: 7
                IslandPreviewButton { objectName: "islandNowPlayingSources"; Layout.fillWidth: true; Layout.minimumWidth: 0; iconName: "music"; iconSize: 14; text: (S.IslandMedia.player ? S.IslandMedia.player.identity || "Media" : "Sources") + "  ⌄"; font.pixelSize: 11; implicitHeight: 31; enabled: root.sources.length > 0; onClicked: root.sourcesExpanded = !root.sourcesExpanded }
                IslandPreviewButton { Layout.fillWidth: true; Layout.minimumWidth: 0; iconName: "volume"; iconSize: 14; text: S.Audio.outputName || "Sound output"; font.pixelSize: 11; implicitHeight: 31; quiet: true; tooltip: "Detailed media controls"; onClicked: root.detailsRequested() }
            }
            Flow {
                Layout.fillWidth: true; Layout.minimumWidth: 0
                visible: root.sourcesExpanded && root.sources.length > 0
                spacing: 6
                Repeater {
                    model: root.sources
                    IslandPreviewButton { required property var modelData; width: Math.min(implicitWidth, content.width); text: modelData.identity || modelData.dbusName; selected: S.IslandMedia.player === modelData; implicitHeight: 30; font.pixelSize: 11; onClicked: { S.IslandMedia.select(modelData); root.sourcesExpanded = false; } }
                }
            }
        }
    }
}
