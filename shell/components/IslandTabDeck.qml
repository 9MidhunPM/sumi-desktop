pragma ComponentBehavior: Bound

import QtQuick
import "../config"

// One horizontal gesture changes one page; vertical scrolling stays with it.
Item {
    id: root
    default property alias pages: content.data
    property int currentIndex: 0
    property bool active: true
    property bool gestureEnabled: true
    property real swipeDistance: 24
    property real wheelDistance: 40
    readonly property int count: content.children.length
    readonly property bool moving: slide.running
    property real offset: currentIndex
    property bool initialized: false
    property bool gestureActive: false
    property bool gestureSwitched: false
    property real pixels: 0
    property real angles: 0
    clip: true
    signal indexRequested(int index)

    function resetGesture() {
        quiet.stop();
        gestureActive = false;
        gestureSwitched = false;
        pixels = 0;
        angles = 0;
    }
    function navigate(delta) {
        if (!active || count < 1) return false;
        const next = Math.max(0, Math.min(count - 1, currentIndex + delta));
        if (next === currentIndex) return false;
        indexRequested(next);
        return true;
    }
    function consumeHorizontal(pixelDeltaX, angleDeltaX, phase = Qt.NoScrollPhase) {
        if (!active) { resetGesture(); return false; }
        if (phase === Qt.ScrollEnd) {
            const used = gestureActive;
            resetGesture();
            return used;
        }
        if (phase === Qt.ScrollMomentum && !gestureActive) return true;
        if (phase === Qt.ScrollBegin) resetGesture();
        gestureActive = true;
        if (phase === Qt.NoScrollPhase) quiet.restart();
        else quiet.stop();
        if (gestureSwitched) return true;
        const pixel = Number(pixelDeltaX) || 0;
        const angle = Number(angleDeltaX) || 0;
        if (pixel) pixels += pixel;
        else angles += angle;
        if (Math.abs(pixels) >= swipeDistance || Math.abs(angles) >= wheelDistance) {
            const distance = Math.abs(pixels) >= swipeDistance ? pixels : angles;
            gestureSwitched = true;
            // Natural horizontal scrolling: content follows the fingers.
            navigate(distance < 0 ? 1 : -1);
        }
        return pixel !== 0 || angle !== 0;
    }
    function handleWheel(pixelX, pixelY, angleX, angleY, phase = Qt.NoScrollPhase) {
        if (phase === Qt.ScrollEnd) return consumeHorizontal(0, 0, phase);
        const x = pixelX || angleX;
        const y = pixelX || pixelY ? pixelY : angleY;
        if (!x || Math.abs(x) <= Math.abs(y) * 1.25) return false;
        return consumeHorizontal(pixelX, angleX, phase);
    }
    function arrange() {
        for (let index = 0; index < content.children.length; index++) {
            const page = content.children[index];
            const position = index;
            page.x = Qt.binding(() => position * root.width);
            page.y = 0;
            page.width = Qt.binding(() => root.width);
            page.height = Qt.binding(() => root.height);
            page.visible = Qt.binding(() => root.active && (root.moving ? Math.abs(position - root.offset) < 1 : root.currentIndex === position));
            page.enabled = Qt.binding(() => root.active && !root.moving && root.currentIndex === position);
        }
    }
    onActiveChanged: {
        if (!active) resetGesture();
        offset = Qt.binding(() => root.currentIndex);
    }
    Component.onCompleted: { arrange(); initialized = true; }
    Behavior on offset {
        enabled: root.initialized && root.active && !Theme.effectiveReducedMotion
        NumberAnimation { id: slide; duration: Theme.batteryMotion ? 120 : 180; easing.type: Easing.OutCubic }
    }
    Timer { id: quiet; interval: 180; onTriggered: root.resetGesture() }
    Item {
        id: content
        x: -root.offset * root.width
        width: root.width * root.count
        height: root.height
        onChildrenChanged: Qt.callLater(root.arrange)
    }
    IslandTabGesture {
        anchors.fill: parent
        z: 1000
        deck: root
        active: root.active && root.gestureEnabled
    }
    Keys.priority: Keys.BeforeItem
    Keys.onPressed: event => {
        if ((event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) && (event.modifiers & Qt.ControlModifier)) {
            navigate((event.modifiers & Qt.ShiftModifier) ? -1 : 1);
            event.accepted = true;
        }
    }
}
