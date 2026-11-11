import QtQuick
import QtQuick.Controls
import "../config"

Slider {
    id: control
    property bool island: false
    property string label: ""
    from: 0
    to: 1
    stepSize: 0.01
    implicitHeight: IslandStyle.target
    padding: 0
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Accessible.name: label
    background: Rectangle {
        x: control.leftPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        width: control.availableWidth
        height: 5
        radius: 3
        color: control.island ? IslandStyle.line : Qt.rgba(Theme.textMain.r, Theme.textMain.g, Theme.textMain.b, 0.18)
        Rectangle {
            width: control.visualPosition * parent.width
            height: parent.height
            radius: parent.radius
            color: control.enabled ? (control.island ? IslandStyle.accent : Theme.textMain) : Theme.textSoft
        }
    }
    handle: Rectangle {
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        y: control.topPadding + (control.availableHeight - height) / 2
        implicitWidth: 14
        implicitHeight: 14
        radius: 7
        color: control.island ? IslandStyle.text : Theme.textMain
        border.width: control.visualFocus ? 2 : 0
        border.color: Theme.accentBlue
    }
}
