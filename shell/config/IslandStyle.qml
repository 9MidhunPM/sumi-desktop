pragma Singleton
import QtQuick

// Shared material and metrics for Sumi's island workspaces. Standalone desktop
// surfaces keep Theme's wallpaper-aware glass while using the same type rhythm.
QtObject {
    readonly property color surface: "#000000"
    readonly property color raised: "#1c1c1f"
    readonly property color hover: "#2c2c30"
    readonly property color line: "#333338"
    readonly property color text: "#f5f5f7"
    readonly property color secondary: "#a9a9b1"
    readonly property color muted: "#909098"
    readonly property color accent: "#ededf0"
    readonly property color accentText: "#17171a"
    readonly property int radius: Metrics.space4
    readonly property int moduleRadius: Metrics.moduleRadius
    readonly property int controlRadius: Metrics.controlRadius
    readonly property int smallRadius: Metrics.compactRadius
    readonly property int outerRadius: Metrics.outerRadius
    readonly property int inset: Metrics.space5
    readonly property int smallGap: Metrics.space2
    readonly property int gap: Metrics.space3
    readonly property int sectionGap: Metrics.space4
    readonly property int target: Metrics.target
    readonly property int smallText: 12
    readonly property int bodyText: 14
    readonly property int headingText: 16
    readonly property int transition: Motion.content
    readonly property int musicTransition: Motion.music
    readonly property int geometryTransition: Motion.geometry
}
