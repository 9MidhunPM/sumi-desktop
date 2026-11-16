pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import "../config"

Singleton {
    id: root
    property bool displayEnabled: true
    property bool playbackActive: Media.playing
    property int consumerSerial: 0
    property var consumers: ({})
    readonly property bool hasVisibleConsumer: Object.keys(consumers).length > 0
    property var samples: []
    property bool sessionLocked: false
    readonly property bool active: displayEnabled && hasVisibleConsumer && playbackActive && Motion.expressive && !Desktop.preview && !sessionLocked
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
    FileView {
        path: (Quickshell.env("XDG_RUNTIME_DIR") || "/run/user/" + Quickshell.env("UID")) + "/sumi/lock-display.json"
        preload: !Desktop.preview
        watchChanges: !Desktop.preview
        printErrors: false
        onLoaded: {
            try {
                const state = JSON.parse(text());
                root.sessionLocked = !!(state.secure || state.pending);
            } catch (error) { /* Keep the last confirmed lock state. */ }
        }
        onFileChanged: reload()
    }
    Process {
        command: ["cava", "-p", Quickshell.shellPath("config/cava.conf")]
        running: root.active
        stdout: SplitParser {
            onRead: line => {
                const values = line.trim().split(/\s+/).map(value => Math.max(0, Math.min(100, Number(value) || 0)));
                if (values.length >= 8) root.samples = values;
            }
        }
    }
}
