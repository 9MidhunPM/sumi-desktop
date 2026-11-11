import QtQuick
import "../config"

Rectangle {
    id: surface
    property bool inset: false
    property bool island: false
    color: island ? (inset ? IslandStyle.raised : IslandStyle.surface) : inset ? Theme.glassInset : Theme.glassFill
    radius: island ? IslandStyle.moduleRadius : Theme.windowRounding
    border.width: Theme.borderWidth
    border.color: island ? IslandStyle.line : inset ? Qt.rgba(1, 1, 1, 0.10) : Theme.glassRim

    // Ordinary Qt primitives keep the glass usable with the software renderer.
    // The native compositor supplies the backdrop blur; these are reflections.
    Rectangle {
        objectName: "glassSheen"
        anchors.fill: parent
        anchors.margins: surface.border.width
        radius: Math.max(0, surface.radius - surface.border.width)
        visible: !surface.island && !surface.inset && surface.color.a > 0.25
        gradient: Gradient {
            GradientStop { position: 0; color: Theme.glassHighlight }
            GradientStop { position: 0.32; color: "transparent" }
            GradientStop { position: 0.74; color: "transparent" }
            GradientStop { position: 1; color: Qt.rgba(1, 1, 1, 0.025) }
        }
    }
}
