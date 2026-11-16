import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"

// One row per device or network: an icon tile, its name and state, and
// optional detail such as battery, signal strength or a secured-network lock.
AbstractButton {
    id: control
    property bool island: false
    readonly property color foreground: island ? IslandStyle.text : Theme.textMain
    readonly property color secondary: island ? IslandStyle.secondary : Theme.textSoft
    readonly property color accent: island ? IslandStyle.accent : Theme.accentBlue
    readonly property color accentForeground: island ? IslandStyle.accentText : Theme.desktopBackground
    property string iconName: ""
    // Legacy icon-font glyph, shown only when no island icon is named.
    property string glyph: ""
    property string subtitle: ""
    property string detail: ""
    // Wi-Fi strength from 0 to 1, or -1 when the row has no signal.
    property real signal: -1
    property bool secure: false
    property bool selected: false
    implicitHeight: Math.max(subtitle.length > 0 ? 56 : 44, contentItem.implicitHeight + 20)
    padding: 10
    font.family: Theme.font
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Accessible.name: text + (subtitle ? ", " + subtitle : "") + (detail ? ", " + detail : "")
    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()
    // Shared press response: in quickly, back with the common bounce.
    scale: Theme.effectiveReducedMotion ? 1 : control.down ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: control.down ? Theme.motionControl : Theme.motionBounce * 0.8; easing.type: Easing.BezierSpline; easing.bezierCurve: control.down ? Motion.standardCurve : Motion.bounceCurve } }
    background: Rectangle {
        radius: IslandStyle.controlRadius
        color: control.island ? (control.down ? IslandStyle.hover : control.hovered ? IslandStyle.raised : "transparent") : control.selected ? Qt.rgba(control.accent.r, control.accent.g, control.accent.b, 0.14) : control.down || control.hovered ? Qt.rgba(control.foreground.r, control.foreground.g, control.foreground.b, 0.07) : "transparent"
        border.width: control.visualFocus ? 2 : 0
        border.color: control.accent
        Behavior on color { ColorAnimation { duration: control.down ? 0 : Theme.motionControl } }
    }
    contentItem: RowLayout {
        spacing: Metrics.space3
        Rectangle {
            visible: control.iconName.length > 0
            Layout.preferredWidth: 32; Layout.preferredHeight: 32
            radius: 9
            color: control.selected ? control.accent : Qt.rgba(control.foreground.r, control.foreground.g, control.foreground.b, 0.1)
            Behavior on color { ColorAnimation { duration: Theme.motionControl } }
            Icon { anchors.centerIn: parent; name: control.iconName; size: 17; color: control.selected ? control.accentForeground : control.foreground }
        }
        Label { visible: control.iconName.length === 0 && control.glyph.length > 0; text: control.glyph; font.pixelSize: 21; color: control.selected ? control.accent : control.secondary }
        ColumnLayout {
            Layout.fillWidth: true; Layout.minimumWidth: 0
            spacing: 2
            Label { text: control.text; color: control.foreground; font.pixelSize: 14; font.weight: Font.Medium; elide: Text.ElideRight; Layout.fillWidth: true }
            Label { visible: control.subtitle.length > 0; text: control.subtitle; font.pixelSize: 12; color: control.secondary; elide: Text.ElideRight; Layout.fillWidth: true }
        }
        Label { visible: control.detail.length > 0; text: control.detail; font.pixelSize: 12; font.features: IslandStyle.figures; color: control.secondary }
        Icon { visible: control.secure; name: "lock"; size: 14; color: control.secondary }
        Row {
            visible: control.signal >= 0
            spacing: 2
            height: 13
            Layout.alignment: Qt.AlignVCenter
            Repeater {
                model: 4
                Rectangle {
                    required property int index
                    width: 3; height: 4 + index * 3; radius: 1.5
                    y: 13 - height
                    color: control.foreground
                    opacity: control.signal >= index / 4 + 0.05 ? 1 : 0.25
                }
            }
        }
        Icon { visible: control.selected; name: "check"; size: 16; color: control.accent }
    }
}
