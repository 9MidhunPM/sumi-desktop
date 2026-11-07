import QtQuick
import "../config"

Rectangle {
    id: surface
    property bool inset: false
    color: inset ? Theme.glassInset : Theme.glassFill
    radius: Theme.windowRounding
    border.width: Theme.borderWidth
    border.color: inset ? Qt.rgba(1, 1, 1, 0.10) : Theme.glassRim

    // Ordinary Qt primitives keep the glass usable with the software renderer.
    // The native compositor supplies the backdrop blur; these are reflections.
    Rectangle {
        objectName: "glassSheen"
        anchors.fill: parent
        anchors.margins: surface.border.width
        radius: Math.max(0, surface.radius - surface.border.width)
        visible: !surface.inset && surface.color.a > 0.25
        gradient: Gradient {
            GradientStop { position: 0; color: Theme.glassHighlight }
            GradientStop { position: 0.32; color: "transparent" }
            GradientStop { position: 0.74; color: "transparent" }
            GradientStop { position: 1; color: Qt.rgba(1, 1, 1, 0.025) }
        }
    }
    Rectangle {
        anchors.fill: parent
        anchors.margins: surface.border.width + 1
        radius: Math.max(0, surface.radius - surface.border.width - 1)
        color: "transparent"
        visible: !surface.inset && surface.color.a > 0.25
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.045)
    }
}
