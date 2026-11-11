pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import "../config"

Button {
    id: control
    property string iconName: "settings"
    property string title: ""
    property string subtitle: ""
    property bool selected: false
    property color activeColor: "#35353e"
    property color glyphColor: "#f6f6f8"
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    padding: Metrics.space3
    Accessible.name: title + (subtitle ? ", " + subtitle : "")
    opacity: enabled ? 1 : .4
    background: Rectangle {
        radius: IslandStyle.moduleRadius
        color: control.selected ? control.activeColor : control.down ? "#3a3b42" : control.hovered ? IslandStyle.hover : IslandStyle.raised
        border.width: control.visualFocus ? 2 : 0
        border.color: IslandStyle.text
        Behavior on color { ColorAnimation { duration: IslandStyle.transition } }
    }
    contentItem: Item {
        Icon { x: 0; y: 1; name: control.iconName; size: 20; color: control.glyphColor }
        Label { objectName: "tileTitle"; anchors { left: parent.left; right: parent.right } y: 25; height: Math.max(0, parent.height - y - status.implicitHeight - 4); text: control.title; font.pixelSize: 11; font.weight: Font.DemiBold; color: IslandStyle.text; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
        Label { id: status; objectName: "tileStatus"; anchors { left: parent.left; right: parent.right; bottom: parent.bottom } visible: text.length > 0; text: control.subtitle; font.pixelSize: 10; color: IslandStyle.secondary }
    }
}
