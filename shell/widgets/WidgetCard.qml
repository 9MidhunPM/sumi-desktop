import QtQuick
import "../config"
import "../components" as C

Item {
    id: root
    property real uiScale: 1
    property bool surface: true
    readonly property color panelColor: Theme.glassFill
    readonly property color mainText: Theme.textMain
    readonly property color secondaryText: Theme.textSoft
    readonly property color warningText: Theme.accentWarn
    default property alias content: contentItem.data
    readonly property real contentWidth: width / Math.max(0.01, uiScale)
    readonly property real contentHeight: height / Math.max(0.01, uiScale)

    Item {
        id: contentItem
        width: root.contentWidth
        height: root.contentHeight
        scale: root.uiScale
        transformOrigin: Item.TopLeft
        C.Surface {
            anchors.fill: parent
            visible: root.surface
            radius: IslandStyle.radius + 8
            color: root.panelColor
        }
    }
}
