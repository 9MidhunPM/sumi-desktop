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
    implicitWidth: tight ? 20 : 22
    implicitHeight: 28
    padding: 0
    hoverEnabled: true
    activeFocusOnTab: true
    Accessible.name: summary
    // Shared press response: in quickly, back with the common bounce.
    scale: Theme.effectiveReducedMotion ? 1 : root.down ? 0.96 : 1
    Behavior on scale { NumberAnimation { duration: root.down ? Theme.motionControl : Theme.motionBounce * 0.8; easing.type: Easing.BezierSpline; easing.bezierCurve: root.down ? Motion.standardCurve : Motion.bounceCurve } }
    background: Rectangle {
        radius: 8
        color: root.down ? Qt.rgba(Theme.textMain.r, Theme.textMain.g, Theme.textMain.b, 0.13) : "transparent"
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.accentBlue
        Behavior on color { ColorAnimation { duration: root.down ? 0 : Theme.motionControl } }
    }
    contentItem: Item {
        Rectangle {
            objectName: "workspaceDot" + (root.entry ? root.entry.id : "")
            anchors.centerIn: parent
            width: root.entry && root.entry.active ? 16 : 6
            height: 6
            radius: 3
            color: root.entry && root.entry.urgent ? Theme.accentWarn : root.entry && root.entry.active ? Theme.accentBlue : Theme.textMain
            opacity: root.entry && (root.entry.active || root.entry.urgent) ? 1 : root.windowCount ? 0.78 : 0.28
            Behavior on width { NumberAnimation { duration: Theme.motionBounce; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bounceCurve } }
            Behavior on opacity { NumberAnimation { duration: Theme.effectiveReducedMotion ? 0 : Theme.motionControl } }
        }
    }
    Keys.onReturnPressed: event => { clicked(); event.accepted = true; }
    Keys.onEnterPressed: event => { clicked(); event.accepted = true; }
    ToolTip.visible: visualFocus
    ToolTip.text: summary
    ToolTip.delay: 600
}
