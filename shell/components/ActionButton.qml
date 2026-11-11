import QtQuick
import QtQuick.Controls
import "../config"

Button {
    id: root
    property bool island: false
    readonly property color foreground: island ? IslandStyle.text : Theme.textMain
    readonly property color secondary: island ? IslandStyle.secondary : Theme.textSoft
    readonly property color accent: island ? IslandStyle.accent : Theme.accentBlue
    readonly property color accentForeground: island ? IslandStyle.accentText : Theme.desktopBackground
    property bool selected: false
    property bool quiet: false
    property string tooltip: ""
    property string iconName: ""
    property real iconSize: 20
    property real iconSpacing: 7
    property color textColor: selected ? root.accentForeground : root.foreground
    property color iconColor: textColor
    font.family: Theme.font
    font.pixelSize: 14
    font.weight: Font.Medium
    readonly property real preferredPadding: iconName.length && !text.length ? 8 : 12
    // Natural width is independent of the padding used by constrained hosts.
    implicitWidth: contentItem.implicitWidth + preferredPadding * 2
    implicitHeight: Math.max(IslandStyle.target, contentItem.implicitHeight + 12)
    leftPadding: Math.max(4, Math.min(preferredPadding, (width - contentItem.implicitWidth) / 2))
    rightPadding: leftPadding
    // Keep short dismiss buttons usable without squeezing the caption to zero.
    topPadding: Math.max(0, Math.min(8, (height - contentItem.implicitHeight) / 2))
    bottomPadding: topPadding
    hoverEnabled: true
    activeFocusOnTab: true
    opacity: enabled ? 1 : 0.4
    scale: Theme.effectiveReducedMotion ? 1 : down ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: root.down ? 0 : Theme.motionControl; easing.type: Easing.OutCubic } }
    background: Rectangle {
        radius: IslandStyle.controlRadius
        color: root.selected ? root.accent
            : root.down ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.13)
            : root.quiet ? "transparent"
            : root.island ? (root.hovered ? IslandStyle.hover : IslandStyle.raised)
            : Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, root.hovered ? 0.09 : 0.05)
        border.width: root.visualFocus ? 2 : root.island || root.quiet || root.selected ? 0 : 1
        border.color: root.visualFocus ? root.accent : Theme.borderSoft
        Behavior on color { ColorAnimation { duration: root.down ? 0 : Theme.motionControl } }
    }
    contentItem: Item {
        implicitWidth: contentRow.implicitWidth
        implicitHeight: Math.max(caption.implicitHeight, root.iconName.length ? root.iconSize : 0)
        Item {
            id: contentRow
            anchors.centerIn: parent
            implicitWidth: (root.iconName.length ? root.iconSize : 0)
                + (root.text.length ? caption.implicitWidth : 0)
                + (root.iconName.length && root.text.length ? root.iconSpacing : 0)
            width: Math.max(root.iconName.length ? root.iconSize : 0, Math.min(parent.width, implicitWidth))
            height: parent.height
            Icon {
                anchors.verticalCenter: parent.verticalCenter
                visible: root.iconName.length > 0
                name: root.iconName
                size: root.iconSize
                color: root.iconColor
            }
            Label {
                id: caption
                x: root.iconName.length ? root.iconSize + root.iconSpacing : 0
                width: Math.max(0, parent.width - x)
                height: parent.height
                visible: root.text.length > 0
                text: root.text
                color: root.textColor
                font: root.font
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
        }
    }
    Keys.onReturnPressed: event => { root.clicked(); event.accepted = true; }
    Keys.onEnterPressed: event => { root.clicked(); event.accepted = true; }
    Accessible.name: tooltip || text || iconName
    ToolTip.visible: visualFocus && tooltip.length > 0
    ToolTip.text: tooltip
    ToolTip.delay: 600
}
