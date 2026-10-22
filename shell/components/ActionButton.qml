import QtQuick
import QtQuick.Controls
import "../config"

Button {
    id: root
    property bool selected: false
    property bool quiet: false
    property string tooltip: ""
    property string iconName: ""
    property real iconSize: 20
    property real iconSpacing: 7
    property color textColor: selected ? Theme.desktopBackground : Theme.textMain
    property color iconColor: textColor
    font.family: Theme.font
    font.pixelSize: 13
    font.weight: Font.Medium
    implicitWidth: contentItem.implicitWidth + leftPadding + rightPadding
    implicitHeight: Math.max(36, contentItem.implicitHeight + 12)
    leftPadding: iconName.length && !text.length ? 8 : 12
    rightPadding: leftPadding
    // Keep short dismiss buttons usable without squeezing the caption to zero.
    topPadding: Math.max(0, Math.min(8, (height - contentItem.implicitHeight) / 2))
    bottomPadding: topPadding
    hoverEnabled: true
    activeFocusOnTab: true
    opacity: enabled ? 1 : 0.4
    scale: Theme.effectiveReducedMotion ? 1 : down ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: Theme.motionControl; easing.type: Easing.OutCubic } }
    background: Rectangle {
        radius: 10
        color: root.selected ? Theme.accentBlue
            : root.down ? Qt.rgba(Theme.textMain.r, Theme.textMain.g, Theme.textMain.b, 0.13)
            : root.quiet ? "transparent"
            : Qt.rgba(Theme.textMain.r, Theme.textMain.g, Theme.textMain.b, root.hovered ? 0.09 : 0.05)
        border.width: root.visualFocus ? 2 : root.quiet || root.selected ? 0 : 1
        border.color: root.visualFocus ? Theme.accentBlue : Theme.borderSoft
        Behavior on color { ColorAnimation { duration: Theme.motionControl } }
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
