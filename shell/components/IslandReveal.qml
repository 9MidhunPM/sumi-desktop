import QtQuick
import QtQuick.Effects
import "../config"

// Island content materializes as the contour opens: it sharpens from a soft
// blur while growing toward full size from the island's top edge. Leaving is
// quicker than arriving, so the contour never closes over visible content.
Item {
    id: root
    property bool shown: false
    // Set to drive presence externally instead of from `shown`.
    property bool manual: false
    property real presence: 0
    // Additional fade owned by the host, such as a route-change morph.
    property real dim: 1
    property real originX: width / 2
    property real originY: 0
    // A fixed layer area keeps blur textures stable while the island morphs;
    // following the animated size would reallocate GPU buffers every frame.
    property rect layerRect: Qt.rect(0, 0, 0, 0)
    readonly property bool depth: Motion.depthEffects && GraphicsInfo.api !== GraphicsInfo.Software
    visible: presence > 0.002
    enabled: shown
    opacity: presence * dim
    transform: Scale {
        origin.x: root.originX; origin.y: root.originY
        xScale: 0.94 + 0.06 * root.presence; yScale: xScale
    }
    layer.enabled: depth && visible && presence < 0.995
    layer.sourceRect: layerRect
    layer.effect: MultiEffect {
        blurEnabled: true
        blur: Math.min(1, (1 - root.presence) * 1.4)
        blurMax: 24
        autoPaddingEnabled: false
    }

    function settle(): void {
        fade.stop();
        presence = shown ? 1 : 0;
    }
    function animate(): void {
        if (manual) return;
        fade.stop();
        const target = shown ? 1 : 0;
        if (Motion.reduced || Math.abs(presence - target) < 0.001) { presence = target; return; }
        fade.delay = shown && presence < 0.05 ? Motion.revealDelay : 0;
        fade.to = target;
        fade.duration = shown ? Motion.reveal : Motion.conceal;
        fade.start();
    }
    onShownChanged: animate()
    Component.onCompleted: if (!manual) presence = shown ? 1 : 0
    SequentialAnimation {
        id: fade
        property int delay: 0
        property real to: 1
        property int duration: 0
        PauseAnimation { duration: fade.delay }
        NumberAnimation {
            target: root; property: "presence"; to: fade.to; duration: fade.duration
            easing.type: Easing.BezierSpline
            // Expressive deceleration for arrival; a brisk ease-out for exits.
            easing.bezierCurve: root.shown ? [0.16, 1, 0.3, 1, 1, 1] : [0.3, 0, 0.6, 1, 1, 1]
        }
    }
}
