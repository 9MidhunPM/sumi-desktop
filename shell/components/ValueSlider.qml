import QtQuick
import QtQuick.Controls
import "../config"

Slider {
    id: control
    from: 0
    to: 1
    focusPolicy: Qt.StrongFocus
    stepSize: (to - from) / 100
    implicitHeight: 34
    background: Rectangle {
        x: control.leftPadding
        y: control.topPadding + control.availableHeight / 2 - height / 2
        width: control.availableWidth
        height: 5
        radius: 3
        color: Theme.borderSoft
        Rectangle { width: control.visualPosition * parent.width; height: parent.height; radius: 3; color: Theme.accentBlue }
    }
    handle: Rectangle {
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        y: control.topPadding + control.availableHeight / 2 - height / 2
        implicitWidth: 16
        implicitHeight: 16
        radius: 8
        color: Theme.textMain
        border.width: control.visualFocus ? 3 : 2
        border.color: Theme.accentBlue
    }
}
