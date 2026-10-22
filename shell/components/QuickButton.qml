import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"

AbstractButton {
    id: control
    property string glyph: ""
    property bool selected: false
    property bool quiet: false
    property bool compact: false
    property string tooltip: ""
    implicitWidth: contentRow.implicitWidth + leftPadding + rightPadding
    implicitHeight: Math.max(compact ? 34 : 40, contentRow.implicitHeight + 12)
    leftPadding: compact ? 10 : 12
    rightPadding: leftPadding
    topPadding: Math.max(0, Math.min(8, (height - contentRow.implicitHeight) / 2))
    bottomPadding: topPadding
    font.family: Theme.font
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Accessible.name: text || tooltip
    opacity: enabled ? 1 : 0.4
    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()
    background: Rectangle {
        radius: control.compact ? 10 : 12
        color: control.selected ? Theme.accentBlue
            : control.down ? Qt.rgba(Theme.textMain.r, Theme.textMain.g, Theme.textMain.b, 0.13)
            : control.quiet ? "transparent"
            : Qt.rgba(Theme.textMain.r, Theme.textMain.g, Theme.textMain.b, control.hovered ? 0.09 : 0.05)
        border.width: control.visualFocus ? 2 : 0
        border.color: Theme.accentBlue
        Behavior on color { ColorAnimation { duration: Theme.motionControl } }
    }
    contentItem: RowLayout {
        id: contentRow
        spacing: 7
        Label { visible: control.glyph.length > 0; text: control.glyph; font.pixelSize: 17; color: control.selected ? Theme.desktopBackground : Theme.textMain }
        Label { visible: control.text.length > 0; text: control.text; Layout.fillWidth: true; Layout.minimumWidth: 0; font.pixelSize: control.compact ? 12 : 13; font.weight: Font.Medium; color: control.selected ? Theme.desktopBackground : Theme.textMain }
    }
    ToolTip.visible: visualFocus && tooltip.length > 0
    ToolTip.text: tooltip
    ToolTip.delay: 600
}
