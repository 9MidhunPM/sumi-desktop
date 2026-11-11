import QtQuick
import "../config"

// Neutral actions shared by the compact island pages.
ActionButton {
    id: control
    island: true
    implicitHeight: 40
    textColor: selected ? IslandStyle.accentText : IslandStyle.text
    background: Rectangle {
        radius: IslandStyle.controlRadius
        color: control.selected ? IslandStyle.accent : control.down ? IslandStyle.hover : control.quiet ? control.hovered ? IslandStyle.hover : "transparent" : control.hovered ? IslandStyle.hover : IslandStyle.raised
        border.width: control.visualFocus ? 2 : 0
        border.color: IslandStyle.text
        Behavior on color { ColorAnimation { duration: control.down ? 0 : Motion.control } }
    }
}
