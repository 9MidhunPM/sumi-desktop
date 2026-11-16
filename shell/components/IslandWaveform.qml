pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import "../config"

// Presentation only: the island host owns spectrum demand and the CAVA process.
// Frequency bands are arranged from the centre outward, so the strongest low
// bands form a calm central swell. Bars ease toward each measured frame and
// settle to small rounded rests in silence; nothing is ever invented.
Item {
    id: root
    property var samples: []
    property bool active: true
    property color tint: IslandStyle.musicTint
    property int barCount: 20
    // Zero lets bars share the available width; otherwise bars keep this width
    // and the group is centred.
    property real barWidth: 0
    property real spacing: 2
    property real restHeight: 2
    property real restOpacity: 1
    implicitWidth: 48
    implicitHeight: 24
    Accessible.role: Accessible.Graphic
    Accessible.name: "Audio waveform"
    readonly property real dpr: Math.max(1, Screen.devicePixelRatio)
    readonly property int count: Math.max(1, barCount)
    readonly property real gap: Math.round(spacing * dpr) / dpr
    readonly property real bar: barWidth > 0 ? Math.max(1 / dpr, Math.round(barWidth * dpr) / dpr)
        : Math.max(1 / dpr, (width - (count - 1) * gap) / count)
    readonly property real span: count * bar + (count - 1) * gap
    readonly property real start: Math.round((width - span) / 2 * dpr) / dpr
    readonly property bool live: active && !!samples && samples.length > 0
    property var targets: []
    property var levels: []

    // Change handlers run before dependent bindings settle, so measure from
    // the source properties directly rather than from derived bindings.
    function measure(): void {
        const total = Math.max(1, barCount);
        const length = active && samples && samples.length ? samples.length : 0;
        // Band k belongs to the k-th position counted from the centre outward.
        const centre = (total - 1) / 2;
        const order = [];
        for (let i = 0; i < total; i++) order.push(i);
        order.sort((a, b) => Math.abs(a - centre) - Math.abs(b - centre) || a - b);
        const next = [];
        for (let position = 0; position < total; position++) {
            if (!length) { next.push(0); continue; }
            const band = order.indexOf(position);
            const first = Math.floor(band * length / total);
            const last = Math.max(first + 1, Math.floor((band + 1) * length / total));
            let sum = 0;
            for (let i = first; i < last; i++) sum += Number(samples[i]) || 0;
            next.push(Math.max(0, Math.min(100, sum / (last - first))));
        }
        targets = next;
        if (Motion.reduced || levels.length !== total) { levels = next.slice(); return; }
        easing.running = true;
    }
    property real pendingStep: 0
    function ease(elapsed: real): void {
        // Samples arrive at 30 Hz. Easing at up to 60 Hz stays smooth without
        // redrawing the island on every frame of a 120 Hz display.
        pendingStep += Math.max(0, elapsed);
        if (pendingStep < 1 / 64) return;
        const step = Math.min(pendingStep, 0.05);
        pendingStep = 0;
        const next = levels.slice();
        let moving = false;
        for (let i = 0; i < next.length; i++) {
            const target = targets[i] || 0, current = next[i] || 0;
            // Fast attack, slightly softer release, like a well-damped meter.
            const rate = target > current ? 30 : 20;
            const value = current + (target - current) * (1 - Math.exp(-rate * step));
            next[i] = Math.abs(target - value) < 0.25 ? target : value;
            if (next[i] !== target) moving = true;
        }
        levels = next;
        if (!moving) easing.running = false;
    }
    onSamplesChanged: measure()
    onActiveChanged: measure()
    onBarCountChanged: measure()
    Component.onCompleted: measure()
    FrameAnimation { id: easing; running: false; onTriggered: root.ease(frameTime) }

    Repeater {
        model: root.count
        Rectangle {
            required property int index
            objectName: "islandSpectrumBar" + index
            readonly property real rest: Math.min(root.restHeight, root.height)
            x: root.start + index * (root.bar + root.gap)
            width: root.bar
            height: Math.max(rest, root.height * (root.levels[index] || 0) / 100)
            y: (root.height - height) / 2
            radius: width / 2
            antialiasing: true
            color: root.tint
            opacity: root.live || height > rest + 0.5 ? 1 : root.restOpacity
            Behavior on opacity { NumberAnimation { duration: Motion.control } }
            Behavior on color { ColorAnimation { duration: Motion.reveal } }
        }
    }
}
