import QtQuick

// A damped spring stepped with its exact closed-form solution on every
// rendered frame. Retargeting keeps the current velocity, so an interrupted
// morph flows into its new destination instead of restarting from rest.
QtObject {
    id: spring
    property real to: 0
    property real value: 0
    property real velocity: 0
    property bool animated: true
    // Growth and settling can have different characters: response is the
    // undamped period in seconds, damping the ratio (1 is critical).
    property real response: 0.46
    property real damping: 0.66
    property real settleResponse: response
    property real settleDamping: 1
    property real precision: 0.05
    property bool growing: true
    readonly property bool running: driver.running
    property bool ready: false

    function snap(): void {
        driver.running = false;
        velocity = 0;
        value = to;
    }
    function retarget(): void {
        if (!ready) return;
        if (!animated) { snap(); return; }
        if (Math.abs(to - value) < precision && Math.abs(velocity) < precision * 8) { snap(); return; }
        growing = to > value;
        driver.running = true;
    }
    function advance(elapsed: real): void {
        const step = Math.max(0, Math.min(elapsed, 0.05));
        const period = Math.max(0.05, growing ? response : settleResponse);
        const zeta = Math.max(0.05, Math.min(1, growing ? damping : settleDamping));
        const omega = 2 * Math.PI / period;
        const offset = value - to;
        const decay = Math.exp(-zeta * omega * step);
        let nextOffset = 0, nextVelocity = 0;
        if (zeta > 0.999) {
            const slope = velocity + omega * offset;
            nextOffset = (offset + slope * step) * decay;
            nextVelocity = (velocity - omega * slope * step) * decay;
        } else {
            const damped = omega * Math.sqrt(1 - zeta * zeta);
            const cosine = Math.cos(damped * step), sine = Math.sin(damped * step);
            const phase = (velocity + zeta * omega * offset) / damped;
            nextOffset = (offset * cosine + phase * sine) * decay;
            nextVelocity = (velocity * cosine - (zeta * omega * phase + damped * offset) * sine) * decay;
        }
        if (Math.abs(nextOffset) < precision && Math.abs(nextVelocity) < precision * 8) { snap(); return; }
        velocity = nextVelocity;
        value = to + nextOffset;
    }
    onToChanged: retarget()
    onAnimatedChanged: if (!animated) snap()
    property FrameAnimation driver: FrameAnimation {
        running: false
        onTriggered: spring.advance(frameTime)
    }
    Component.onCompleted: { value = to; ready = true; }
}
