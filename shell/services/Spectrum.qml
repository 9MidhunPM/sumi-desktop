pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import "../config"

Singleton {
    id: root
    property bool displayEnabled: true
    property int consumerSerial: 0
    property var consumers: ({})
    readonly property bool hasVisibleConsumer: Object.keys(consumers).length > 0
    property var samples: []
    readonly property bool active: displayEnabled && hasVisibleConsumer && Media.playing && Motion.expressive && !Desktop.preview
    onActiveChanged: if (!active) samples = []

    function createConsumer(): int { return ++consumerSerial; }
    function setDemand(id: int, value: bool): void {
        if (!id) return;
        const next = Object.assign({}, consumers);
        if (value) next[id] = true;
        else delete next[id];
        consumers = next;
    }

    // One PipeWire FFT process shared by every display, asleep when paused.
    Process {
        command: ["cava", "-p", Quickshell.shellPath("config/cava.conf")]
        running: root.active
        stdout: SplitParser {
            onRead: line => {
                const values = line.trim().split(/\s+/).map(value => Math.max(0, Math.min(100, Number(value) || 0)));
                if (values.length === 20) root.samples = values;
            }
        }
    }
}
