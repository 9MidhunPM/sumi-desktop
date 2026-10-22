import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"

AbstractButton {
    id: control
    property string glyph: ""
    property string subtitle: ""
    property bool selected: false
    implicitHeight: Math.max(subtitle.length > 0 ? 52 : 44, contentItem.implicitHeight + 20)
    padding: 10
    font.family: Theme.font
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Accessible.name: text + (subtitle ? ", " + subtitle : "")
    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()
    background: Rectangle {
        radius: 12
        color: control.selected ? Qt.rgba(Theme.accentBlue.r, Theme.accentBlue.g, Theme.accentBlue.b, 0.14) : control.down || control.hovered ? Qt.rgba(Theme.textMain.r, Theme.textMain.g, Theme.textMain.b, 0.07) : "transparent"
        border.width: control.visualFocus ? 2 : 0
        border.color: Theme.accentBlue
        Behavior on color { ColorAnimation { duration: Theme.motionControl } }
    }
    contentItem: RowLayout {
        spacing: 12
        Label { visible: control.glyph.length > 0; text: control.glyph; font.pixelSize: 21; color: control.selected ? Theme.accentBlue : Theme.textSoft }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 3
            Label { text: control.text; color: Theme.textMain; font.pixelSize: 13; font.weight: Font.Medium; Layout.fillWidth: true }
            Label { visible: control.subtitle.length > 0; text: control.subtitle; font.pixelSize: 11; color: Theme.textSoft; Layout.fillWidth: true }
        }
        Label { visible: control.selected; text: "󰄬"; color: Theme.accentBlue; font.pixelSize: 17 }
    }
}
