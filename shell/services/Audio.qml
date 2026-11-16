pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Services.Pipewire as Pw
import Quickshell.Hyprland

Singleton {
    id: root
    readonly property bool ready: Pw.Pipewire.ready
    readonly property var sink: Pw.Pipewire.defaultAudioSink
    readonly property var source: Pw.Pipewire.defaultAudioSource
    readonly property bool hasOutput: ready && !!sink && !!sink.audio
    readonly property bool hasInput: ready && !!source && !!source.audio
    readonly property string outputName: hasOutput ? label(sink) : "No output device"
    readonly property string inputName: hasInput ? label(source) : "No microphone"
    // PipeWire's node.nick is the short name people recognise ("Headphones", "HDMI 1").
    function label(node: var): string { return node ? String(node.nickname || node.description || node.name || "") : ""; }
    function isDisplayAudio(node: var): bool { return !!node && /HDMI|DisplayPort/i.test(String(node.nickname || "") + " " + String(node.description || "")); }
    function deviceIcon(node: var): string {
        const name = label(node).toLowerCase();
        return isDisplayAudio(node) ? "display" : /head|ear|bud/.test(name) ? "headphones" : node && !node.isSink ? "microphone" : "volume";
    }
    // Display audio only carries sound while an external screen is attached.
    readonly property bool externalDisplay: Hyprland.monitors.values.some(monitor => !/^eDP/.test(String(monitor.name || "")))
    readonly property real volume: sink && sink.audio ? sink.audio.volume : 0
    readonly property bool muted: sink && sink.audio ? sink.audio.muted : false
    readonly property real sourceVolume: source && source.audio ? source.audio.volume : 0
    readonly property bool sourceMuted: source && source.audio ? source.audio.muted : false
    readonly property var sinks: Pw.Pipewire.nodes.values.filter(node => node.audio && node.isSink && !node.isStream)
    readonly property var sources: Pw.Pipewire.nodes.values.filter(node => node.audio && !node.isSink && !node.isStream)
    readonly property var visibleSinks: sinks.filter(node => !isDisplayAudio(node) || externalDisplay || node === sink)

    // PipeWire nodes must be tracked for audio controls to remain bound.
    Pw.PwObjectTracker { objects: [root.sink, root.source].filter(node => node !== null) }

    function setVolume(value: real): void {
        if (sink && sink.audio && !Desktop.preview) sink.audio.volume = Math.max(0, Math.min(1, value));
    }
    function changeVolume(delta: real): void { setVolume(volume + delta); }
    function toggleMute(): void {
        if (sink && sink.audio && !Desktop.preview) sink.audio.muted = !sink.audio.muted;
    }
    function setSourceVolume(value: real): void {
        if (source && source.audio && !Desktop.preview) source.audio.volume = Math.max(0, Math.min(1, value));
    }
    function toggleSourceMute(): void {
        if (source && source.audio && !Desktop.preview) source.audio.muted = !source.audio.muted;
    }
    function selectSink(node: var): void { if (node && !Desktop.preview) Pw.Pipewire.preferredDefaultAudioSink = node; }
    function selectSource(node: var): void { if (node && !Desktop.preview) Pw.Pipewire.preferredDefaultAudioSource = node; }
    function openManager(): void { Desktop.action("audio-manager", []); }
}
