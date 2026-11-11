pragma ComponentBehavior: Bound
import QtQuick
import "OrbMath.js" as OrbMath

// The same envelope, projection and painting code drives the web canvas.
Item {
    id: orb
    property real level: 0
    property bool active: false
    property bool processing: false
    property bool reducedMotion: false
    property bool effectsActive: true
    property color accent: "#38bdf8"
    property int particleCount: width < 60 ? 64 : 300
    property var motion: OrbMath.createState()
    property real phase: 0
    property real displayedLevel: 0
    readonly property bool rendering: visible && effectsActive && (active || processing)
    readonly property real visualRadius: OrbMath.radius(Math.min(width, height), displayedLevel, reducedMotion)
    implicitWidth: 160
    implicitHeight: 160
    Accessible.role: Accessible.Graphic
    Accessible.name: processing && !active ? "Thursday is processing" : "Thursday audio level"
    Accessible.description: "A circular particle visualizer responding to measured audio"
    function rgb() { return Math.round(accent.r * 255) + ',' + Math.round(accent.g * 255) + ',' + Math.round(accent.b * 255) }
    function reset() {
        if (!rendering) OrbMath.reset(motion)
        else OrbMath.sample(motion, active ? level : 0, Date.now())
        if (reducedMotion) motion.displayedLevel = active ? OrbMath.normalized(level) : 0
        displayedLevel = motion.displayedLevel
        if (!rendering || reducedMotion) drawing.requestPaint()
    }
    function advance() {
        if (!OrbMath.advance(motion, Date.now(), level, active, processing, reducedMotion)) return
        phase = motion.phase
        displayedLevel = motion.displayedLevel
        drawing.requestPaint()
    }
    onLevelChanged: reset()
    onActiveChanged: reset()
    onRenderingChanged: reset()
    onReducedMotionChanged: reset()
    onAccentChanged: { glow.requestPaint(); drawing.requestPaint() }
    FrameAnimation { running: orb.rendering && !orb.reducedMotion; onTriggered: orb.advance() }
    Canvas {
        id: glow
        anchors.centerIn: parent
        width: Math.min(orb.width, orb.height); height: width
        scale: Math.min(1, orb.visualRadius / Math.max(1, width * 0.34))
        opacity: orb.rendering ? 0.8 + orb.displayedLevel * 0.2 : 0.4
        onWidthChanged: requestPaint()
        onPaint: { const ctx = getContext("2d"); ctx.reset(); OrbMath.paintGlow(ctx, width, orb.rgb()) }
    }
    Canvas {
        id: drawing
        anchors.fill: parent
        property var points: OrbMath.points(orb.particleCount)
        Component.onCompleted: requestPaint()
        onPointsChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d"); ctx.reset()
            OrbMath.paintParticles(ctx, width, height, points, orb.phase, orb.displayedLevel,
                                   orb.reducedMotion, orb.rgb(), orb.rendering)
        }
    }
}
