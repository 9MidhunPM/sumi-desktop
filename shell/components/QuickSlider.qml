import QtQuick
import QtQuick.Controls
import "../config"

Slider {
    id: control
    property string label: ""
    from: 0
    to: 1
    stepSize: 0.01
    implicitHeight: 42
    padding: 0
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Accessible.name: label
    background: Rectangle {
        x: control.leftPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        width: control.availableWidth
        height: 36
        radius: 12
        color: Qt.rgba(Theme.textMain.r, Theme.textMain.g, Theme.textMain.b, 0.075)
        border.width: control.visualFocus ? 2 : 0
        border.color: Theme.accentBlue
        Rectangle {
            width: Math.max(24, control.visualPosition * parent.width)
            height: parent.height
            radius: parent.radius
            color: control.enabled ? Theme.accentBlue : Theme.textSoft
        }
    }
    handle: Rectangle {
        x: control.leftPadding + Math.max(9, control.visualPosition * (control.availableWidth - width) - 8)
        y: control.topPadding + (control.availableHeight - height) / 2
        implicitWidth: 4
        implicitHeight: control.pressed ? 21 : 17
        radius: 2
        color: Theme.desktopBackground
        Behavior on implicitHeight { NumberAnimation { duration: Theme.motionControl } }
    }
}
