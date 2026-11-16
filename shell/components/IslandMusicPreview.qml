pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../config"
import "../services" as S
import "MediaTime.js" as MediaTime

// The host renders artwork, track information and spectrum in the header.
ColumnLayout {
    id: root
    property bool active: false
    property real mediaPosition: 0
    property var samples: []
    property bool showTransport: true
    property bool showFooter: true
    property alias primaryControl: play
    readonly property real trackLength: S.IslandMedia.player && S.IslandMedia.player.lengthSupported ? Math.max(0, S.IslandMedia.player.length) : 0
    signal detailsRequested()
    spacing: 0
    function time(seconds) { return MediaTime.format(seconds); }
    RowLayout {
        Layout.fillWidth: true; Layout.minimumWidth: 0
        implicitHeight: 24; spacing: 8
        Label { objectName: "islandPreviewPosition"; text: S.IslandMedia.available ? root.time(root.mediaPosition) : "--:--"; font.pixelSize: IslandStyle.captionText; font.features: IslandStyle.figures; color: IslandStyle.secondary }
        QuickSlider {
            id: seek
            objectName: "islandPreviewSeek"
            Layout.fillWidth: true; Layout.minimumWidth: 0
            implicitHeight: 24
            label: "Track position"
            to: Math.max(1, root.trackLength)
            value: root.mediaPosition
            stepSize: 1
            enabled: root.active && !!S.IslandMedia.player && S.IslandMedia.player.canSeek && root.trackLength > 0
            onMoved: S.IslandMedia.seek(value)
            // The track thickens under the pointer to invite scrubbing.
            readonly property bool engaged: hovered || pressed || visualFocus
            background: Rectangle {
                y: (seek.height - height) / 2; width: seek.width
                height: seek.engaged ? 6 : 4; radius: height / 2; color: IslandStyle.line
                Behavior on height { NumberAnimation { duration: Motion.control; easing.type: Easing.OutCubic } }
                Rectangle { width: seek.visualPosition * parent.width; height: parent.height; radius: parent.radius; color: IslandStyle.text }
            }
            handle: Rectangle {
                x: seek.visualPosition * (seek.width - width); y: (seek.height - height) / 2
                width: seek.pressed ? 12 : 10; height: width; radius: width / 2; color: IslandStyle.text
                opacity: seek.visualFocus || seek.pressed ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Motion.control } }
                Behavior on width { NumberAnimation { duration: Motion.control; easing.type: Easing.OutCubic } }
            }
        }
        Label { objectName: "islandPreviewDuration"; text: root.trackLength > 0 ? root.time(root.trackLength) : "--:--"; font.pixelSize: IslandStyle.captionText; font.features: IslandStyle.figures; color: IslandStyle.secondary }
    }
    Item { Layout.fillWidth: true; Layout.preferredHeight: 40; visible: !root.showTransport && root.showFooter }
    RowLayout {
        objectName: "islandPreviewFooter"
        visible: root.showFooter || root.showTransport
        Layout.fillWidth: true; Layout.minimumWidth: 0; implicitHeight: 40; spacing: 2
        Label { Layout.fillWidth: true; Layout.minimumWidth: 0; visible: root.width >= 360; text: S.Audio.outputName || "Sound output"; font.pixelSize: IslandStyle.captionText; color: IslandStyle.secondary; elide: Text.ElideRight }
        Item { Layout.fillWidth: true; Layout.minimumWidth: 0; visible: root.width < 360 }
        IslandPreviewButton { visible: root.showTransport; objectName: "islandPreviewPrevious"; iconName: "backward"; iconSize: 21; tooltip: "Previous track"; quiet: true; implicitWidth: 40; implicitHeight: 40; enabled: root.active && !!S.IslandMedia.player && S.IslandMedia.player.canGoPrevious; onClicked: S.IslandMedia.previous() }
        IslandPreviewButton { id: play; visible: root.showTransport; objectName: "islandPreviewPlay"; iconName: S.IslandMedia.playing ? "pause-fill" : "play-fill"; iconSize: 24; tooltip: S.IslandMedia.playing ? "Pause" : "Play"; quiet: true; implicitWidth: 40; implicitHeight: 40; enabled: root.active && !!S.IslandMedia.player && S.IslandMedia.player.canTogglePlaying; onClicked: S.IslandMedia.toggle() }
        IslandPreviewButton { visible: root.showTransport; objectName: "islandPreviewNext"; iconName: "forward"; iconSize: 21; tooltip: "Next track"; quiet: true; implicitWidth: 40; implicitHeight: 40; enabled: root.active && !!S.IslandMedia.player && S.IslandMedia.player.canGoNext; onClicked: S.IslandMedia.next() }
        Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }
        ActionButton { objectName: "islandPreviewFullPlayer"; text: "Full player"; font.pixelSize: IslandStyle.captionText; quiet: true; textColor: IslandStyle.secondary; width: 90; height: 40; Layout.preferredWidth: 90; Layout.preferredHeight: 40; onClicked: root.detailsRequested() }
    }
}
