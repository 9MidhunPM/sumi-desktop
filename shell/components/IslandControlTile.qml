pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls

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
    padding: 14
    Accessible.name: title + (subtitle ? ", " + subtitle : "")
    opacity: enabled ? 1 : .4
    background: Rectangle {
        radius: 22
        color: control.selected ? control.activeColor : control.down ? "#3a3b42" : control.hovered ? "#34353c" : "#24252a"
        border.width: control.visualFocus ? 2 : 0
        border.color: "#ffffff"
        Behavior on color { ColorAnimation { duration: 100 } }
    }
    contentItem: Item {
        Icon { x: 0; y: 1; name: control.iconName; size: 25; color: control.glyphColor }
        Label { anchors { left: parent.left; right: parent.right; bottom: parent.bottom; bottomMargin: control.subtitle ? 16 : 0 } text: control.title; font.pixelSize: 12; font.weight: Font.DemiBold; color: "#f8f8fb" }
        Label { anchors { left: parent.left; right: parent.right; bottom: parent.bottom } visible: text.length > 0; text: control.subtitle; font.pixelSize: 10; color: "#c7c7d0" }
    }
}
