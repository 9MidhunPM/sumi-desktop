import QtQuick

// Neutral actions shared by the compact island pages.
ActionButton {
    id: control
    textColor: selected ? "#202027" : "#f1f1f6"
    background: Rectangle {
        radius: 15
        color: control.selected ? "#f5f5f8" : control.quiet ? control.hovered ? "#34353d" : "transparent" : control.down ? "#494a54" : "#303138"
        border.width: control.visualFocus ? 2 : 0
        border.color: "#ffffff"
    }
}
