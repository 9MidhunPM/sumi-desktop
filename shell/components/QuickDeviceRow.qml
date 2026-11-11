import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"

AbstractButton {
    id: control
    property bool island: false
    readonly property color foreground: island ? IslandStyle.text : Theme.textMain
    readonly property color secondary: island ? IslandStyle.secondary : Theme.textSoft
    readonly property color accent: island ? IslandStyle.accent : Theme.accentBlue
    readonly property color accentForeground: island ? IslandStyle.accentText : Theme.desktopBackground
    property string glyph: ""
    property string subtitle: ""
    property bool selected: false
    implicitHeight: Math.max(subtitle.length > 0 ? 62 : 44, contentItem.implicitHeight + 24)
    padding: 12
    font.family: Theme.font
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Accessible.name: text + (subtitle ? ", " + subtitle : "")
    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()
    background: Rectangle {
        radius: IslandStyle.controlRadius
        color: control.island ? (control.selected || control.down || control.hovered ? IslandStyle.hover : "transparent") : control.selected ? Qt.rgba(control.accent.r, control.accent.g, control.accent.b, 0.14) : control.down || control.hovered ? Qt.rgba(control.foreground.r, control.foreground.g, control.foreground.b, 0.07) : "transparent"
        border.width: control.visualFocus ? 2 : 0
        border.color: control.accent
        Behavior on color { ColorAnimation { duration: control.down || control.selected ? 0 : Theme.motionControl } }
    }
    contentItem: RowLayout {
        spacing: 12
        Label { visible: control.glyph.length > 0; text: control.glyph; font.pixelSize: 21; color: control.selected ? control.accent : control.secondary }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 3
            Label { text: control.text; color: control.foreground; font.pixelSize: 14; font.weight: Font.Medium; Layout.fillWidth: true }
            Label { visible: control.subtitle.length > 0; text: control.subtitle; font.pixelSize: 12; color: control.secondary; Layout.fillWidth: true }
        }
        Label { visible: control.selected; text: "󰄬"; color: control.accent; font.pixelSize: 17 }
    }
}
