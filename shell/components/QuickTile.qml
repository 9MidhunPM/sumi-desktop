import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"

AbstractButton {
    id: control
    property string glyph: ""
    property string subtitle: ""
    property bool selected: false
    property bool disclosure: false
    property string secondaryText: ""
    property string secondaryLabel: ""
    property bool secondaryEnabled: true
    signal secondaryClicked()
    implicitWidth: 180
    implicitHeight: Math.max(88, contentItem.implicitHeight + 24)
    padding: 12
    font.family: Theme.font
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Accessible.name: text + ", " + subtitle
    Accessible.description: disclosure ? "Open " + text + " settings" : "Toggle " + text
    opacity: enabled ? 1 : 0.45
    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()
    background: Rectangle {
        radius: 15
        color: control.selected ? Qt.rgba(Theme.accentBlue.r, Theme.accentBlue.g, Theme.accentBlue.b, control.down ? 0.27 : control.hovered ? 0.23 : 0.17) : Qt.rgba(Theme.textMain.r, Theme.textMain.g, Theme.textMain.b, control.down ? 0.13 : control.hovered ? 0.10 : 0.055)
        border.width: control.visualFocus ? 2 : 0
        border.color: Theme.accentBlue
        Behavior on color { ColorAnimation { duration: Theme.motionControl } }
    }
    contentItem: ColumnLayout {
        spacing: 6
        RowLayout {
            Layout.fillWidth: true
            Label { text: control.glyph; font.pixelSize: 22; color: control.selected ? Theme.accentBlue : Theme.textSoft; Layout.fillWidth: true }
            Label { visible: control.disclosure && !control.secondaryText; text: "›"; font.pixelSize: 21; color: Theme.textSoft }
            Rectangle { visible: !control.disclosure && !control.secondaryText && control.selected; implicitWidth: 6; implicitHeight: 6; radius: 3; color: Theme.accentBlue }
            QuickButton {
                objectName: control.objectName + "Toggle"
                visible: control.secondaryText.length > 0
                enabled: control.secondaryEnabled
                text: control.secondaryText
                tooltip: control.secondaryLabel
                Accessible.name: control.secondaryLabel
                compact: true
                selected: control.selected
                onClicked: control.secondaryClicked()
            }
        }
        ColumnLayout {
            spacing: 1
            Layout.fillWidth: true
            Label { text: control.text; color: Theme.textMain; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true }
            Label { text: control.subtitle; font.pixelSize: 11; color: Theme.textSoft; Layout.fillWidth: true }
        }
    }
}
