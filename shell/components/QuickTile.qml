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
    // Island icon name; preferred over the legacy icon-font glyph.
    property string iconName: ""
    property string subtitle: ""
    property bool selected: false
    property bool disclosure: false
    property string secondaryText: ""
    property string secondaryLabel: ""
    property bool secondaryEnabled: true
    signal secondaryClicked()
    implicitWidth: 180
    implicitHeight: Math.max(96, contentItem.implicitHeight + topPadding + bottomPadding)
    padding: Metrics.space4
    font.family: Theme.font
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Accessible.name: text + ", " + subtitle
    Accessible.description: disclosure ? "Open " + text + " settings" : "Toggle " + text
    opacity: enabled ? 1 : 0.45
    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()
    // Shared press response: in quickly, back with the common bounce.
    scale: Theme.effectiveReducedMotion ? 1 : control.down ? 0.96 : 1
    Behavior on scale { NumberAnimation { duration: control.down ? Theme.motionControl : Theme.motionBounce * 0.8; easing.type: Easing.BezierSpline; easing.bezierCurve: control.down ? Motion.standardCurve : Motion.bounceCurve } }
    background: Rectangle {
        radius: IslandStyle.moduleRadius
        color: control.island ? (control.selected || control.down || control.hovered ? IslandStyle.hover : IslandStyle.raised) : control.selected ? Qt.rgba(control.accent.r, control.accent.g, control.accent.b, control.down ? 0.27 : control.hovered ? 0.23 : 0.17) : Qt.rgba(control.foreground.r, control.foreground.g, control.foreground.b, control.down ? 0.13 : control.hovered ? 0.10 : 0.055)
        border.width: control.visualFocus ? 2 : 0
        border.color: control.accent
        Behavior on color { ColorAnimation { duration: control.down || control.selected ? 0 : Theme.motionControl } }
    }
    contentItem: ColumnLayout {
        spacing: 6
        RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true; implicitHeight: 24
                Icon { visible: control.iconName.length > 0; name: control.iconName; size: 22; color: control.selected ? control.accent : control.secondary }
                Label { visible: control.iconName.length === 0; text: control.glyph; font.pixelSize: 22; color: control.selected ? control.accent : control.secondary }
            }
            Label { visible: control.disclosure && !control.secondaryText; text: "›"; font.pixelSize: 21; color: control.secondary }
            Rectangle { visible: !control.disclosure && !control.secondaryText && control.selected; implicitWidth: 6; implicitHeight: 6; radius: 3; color: control.accent }
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
            Label { text: control.text; color: control.foreground; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
            Label { text: control.subtitle; font.pixelSize: 12; color: control.secondary; Layout.fillWidth: true; elide: Text.ElideRight }
        }
    }
}
