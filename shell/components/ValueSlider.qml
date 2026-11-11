import QtQuick
import QtQuick.Controls
import "../config"

Slider {
    id: control
    property bool island: false
    readonly property color foreground: island ? IslandStyle.text : Theme.textMain
    readonly property color secondary: island ? IslandStyle.secondary : Theme.textSoft
    readonly property color accent: island ? IslandStyle.accent : Theme.accentBlue
    readonly property color accentForeground: island ? IslandStyle.accentText : Theme.desktopBackground
    from: 0
    to: 1
    focusPolicy: Qt.StrongFocus
    stepSize: (to - from) / 100
    implicitHeight: IslandStyle.target
    background: Rectangle {
        x: control.leftPadding
        y: control.topPadding + control.availableHeight / 2 - height / 2
        width: control.availableWidth
        height: 5
        radius: 3
        color: control.island ? IslandStyle.line : Theme.borderSoft
        Rectangle { width: control.visualPosition * parent.width; height: parent.height; radius: 3; color: control.accent }
    }
    handle: Rectangle {
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        y: control.topPadding + control.availableHeight / 2 - height / 2
        implicitWidth: 14
        implicitHeight: 14
        radius: 7
        color: control.foreground
        border.width: control.visualFocus ? 2 : 0
        border.color: control.accent
    }
}
