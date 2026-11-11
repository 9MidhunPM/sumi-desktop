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
        radius: control.compact ? IslandStyle.smallRadius : IslandStyle.controlRadius
        color: control.selected ? control.accent
            : control.down ? Qt.rgba(control.foreground.r, control.foreground.g, control.foreground.b, 0.13)
            : control.quiet ? "transparent"
            : control.island ? (control.hovered ? IslandStyle.hover : IslandStyle.raised)
            : Qt.rgba(control.foreground.r, control.foreground.g, control.foreground.b, control.hovered ? 0.09 : 0.05)
        border.width: control.visualFocus ? 2 : 0
        border.color: control.accent
        Behavior on color { ColorAnimation { duration: control.down || control.selected ? 0 : Theme.motionControl } }
    }
    contentItem: RowLayout {
        id: contentRow
        spacing: Metrics.space2
        Label { visible: control.glyph.length > 0; text: control.glyph; font.pixelSize: 17; color: control.selected ? control.accentForeground : control.foreground }
        Label { visible: control.text.length > 0; text: control.text; Layout.fillWidth: true; Layout.minimumWidth: 0; font.pixelSize: control.compact ? 12 : 14; font.weight: Font.Medium; color: control.selected ? control.accentForeground : control.foreground }
    }
    ToolTip.visible: visualFocus && tooltip.length > 0
    ToolTip.text: tooltip
    ToolTip.delay: 600
}
