import QtQuick
import QtQuick.Shapes
import QtQuick.Window
import "../config"
import "IslandContour.js" as Contour

// A single exterior contour keeps the shoulders and body seam-free. It is
// rendered as GPU curves, so a morph only re-tessellates a short path instead
// of repainting a window-sized texture on every frame.
Shape {
    id: root
    property real bodyWidth: 176
    property real bodyHeight: 36
    property real headerWidth: bodyWidth
    property real headerHeight: 36
    property bool notch: false
    property bool expanded: false
    property bool focused: false
    // Radii follow the live height, so corners never jump between states.
    readonly property real bottomRadius: Math.min(IslandStyle.outerRadius, bodyHeight / 2)
    readonly property real topRadius: Math.min(24, bodyWidth / 2, bodyHeight / 2)
    readonly property string contour: Contour.path(width, bodyWidth, bodyHeight, notch, bottomRadius, topRadius,
        IslandStyle.shoulderRadius, IslandStyle.cornerSmoothing)
    readonly property real hairline: 1 / Math.max(1, Screen.devicePixelRatio)
    preferredRendererType: Shape.CurveRenderer

    ShapePath {
        strokeWidth: -1
        fillColor: IslandStyle.surface
        PathSvg { path: root.contour }
    }
    // A fine rim catches light along the lower lip and fades toward the bezel,
    // keeping the outline continuous without reading as a drawn border.
    ShapePath {
        fillColor: "transparent"
        strokeColor: "white"
        strokeWidth: root.hairline
        joinStyle: ShapePath.RoundJoin
        capStyle: ShapePath.RoundCap
        strokeGradient: LinearGradient {
            x1: 0; y1: 0; x2: 0; y2: Math.max(1, root.bodyHeight)
            GradientStop { position: 0; color: root.focused ? IslandStyle.rimFocusTop : IslandStyle.rimTop }
            GradientStop { position: 1; color: root.focused ? IslandStyle.rimFocusBottom : IslandStyle.rimBottom }
        }
        PathSvg { path: root.contour }
    }
}
