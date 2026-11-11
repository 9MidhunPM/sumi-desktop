pragma ComponentBehavior: Bound
import QtQuick
import "../config"

// Presentation only: the island host owns spectrum demand and the CAVA process.
Item {
    id: root
    property var samples: []
    property bool active: true
    property color tint: "#e7a88f"
    property int barCount: 20
    implicitWidth: 48
    implicitHeight: 24
    Accessible.role: Accessible.Graphic
    Accessible.name: "Audio waveform"
    Row {
        anchors.fill: parent
        spacing: 2
        Repeater {
            model: Math.max(1, root.barCount)
            Rectangle {
                required property int index
                objectName: "islandSpectrumBar" + index
                readonly property int start: Math.floor(index * root.samples.length / Math.max(1, root.barCount))
                readonly property int end: Math.max(start + 1, Math.floor((index + 1) * root.samples.length / Math.max(1, root.barCount)))
                readonly property real magnitude: {
                    if (!root.active || !root.samples || !root.samples.length) return 0;
                    let total = 0;
                    for (let i = start; i < end; ++i) total += Number(root.samples[i]) || 0;
                    return Math.max(0, Math.min(100, total / (end - start)));
                }
                width: Math.max(1, (root.width - (root.barCount - 1) * 2) / root.barCount)
                height: Math.max(2, root.height * magnitude / 100)
                y: (root.height - height) / 2
                radius: width / 2
                color: root.tint
                Behavior on height { NumberAnimation { duration: Theme.effectiveReducedMotion ? 0 : 90; easing.type: Easing.OutQuad } }
            }
        }
    }
}
