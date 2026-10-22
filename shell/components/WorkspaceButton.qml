pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import "../config"

Button {
    id: root
    required property var entry
    property bool tight: false
    readonly property int windowCount: Math.max(0, Math.floor(Number(entry && entry.windowCount) || 0))
    readonly property string summary: "Workspace " + (entry ? entry.name : "") + (windowCount ? " · " + windowCount + " window" + (windowCount === 1 ? "" : "s") : " · empty")
    objectName: "workspaceButton" + (entry ? entry.id : "")
    implicitWidth: Math.max(tight ? 22 : 32, windowDots.implicitWidth + 12)
    implicitHeight: 28
    padding: 0
    hoverEnabled: true
    activeFocusOnTab: true
    Accessible.name: summary
    background: Rectangle {
        radius: 8
        color: root.entry && root.entry.active ? Qt.rgba(Theme.accentBlue.r, Theme.accentBlue.g, Theme.accentBlue.b, root.down ? 0.26 : 0.18)
            : root.down ? Qt.rgba(Theme.textMain.r, Theme.textMain.g, Theme.textMain.b, 0.13) : "transparent"
        border.width: root.visualFocus ? 2 : root.entry && root.entry.urgent ? 1 : 0
        border.color: root.entry && root.entry.urgent ? Theme.accentWarn : Theme.accentBlue
        Behavior on color { ColorAnimation { duration: Theme.motionControl } }
    }
    contentItem: Item {
        Label {
            objectName: "workspaceNumber" + (root.entry ? root.entry.id : "")
            anchors.centerIn: parent
            height: 18
            text: root.entry ? root.entry.name : ""
            font.pixelSize: 13
            font.weight: root.entry && root.entry.active ? Font.Bold : Font.Medium
            color: root.entry && root.entry.urgent ? Theme.accentWarn : root.entry && root.entry.active ? Theme.accentBlue : root.windowCount ? Theme.textMain : Theme.textSoft
            verticalAlignment: Text.AlignVCenter
        }
        Row {
            id: windowDots
            objectName: "workspaceOccupancy" + (root.entry ? root.entry.id : "")
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 1
            height: 3
            spacing: 3
            visible: root.windowCount > 0
            Repeater {
                model: root.windowCount
                Rectangle {
                    required property int index
                    objectName: "workspaceWindowDot" + (root.entry ? root.entry.id : "") + "-" + index
                    width: 3; height: 3; radius: 1.5
                    color: root.entry && root.entry.urgent ? Theme.accentWarn : Theme.accentBlue
                }
            }
        }
    }
    Keys.onReturnPressed: event => { clicked(); event.accepted = true; }
    Keys.onEnterPressed: event => { clicked(); event.accepted = true; }
    ToolTip.visible: visualFocus
    ToolTip.text: summary
    ToolTip.delay: 600
}
