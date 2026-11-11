pragma ComponentBehavior: Bound
import QtQuick
import "../config"
import "../integrations" as Native

// Voice feedback keeps recognized text readable beside the measured audio orb.
Item {
    id: root
    property string phase: "listening"
    property string partialTranscript: ""
    property string finalTranscript: ""
    property string answer: ""
    property real level: 0
    property bool active: false
    signal openRequested()
    implicitHeight: phase === "speaking" || phase === "reply" ? 130 : 96
    visible: active
    enabled: active
    readonly property bool replying: phase === "speaking" || phase === "reply"
    readonly property string phaseLabel: phase === "listening" ? "Listening" : phase === "transcribing" ? "Transcribing…" : phase === "error" ? "Could not hear you" : replying ? "Thursday · " + (phase === "speaking" ? "Speaking" : "Reply") : "Heard · Thinking"
    readonly property string recognized: finalTranscript || partialTranscript
    readonly property real orbSize: Math.max(0, Math.min(120, width * 0.36, height - 32))
    readonly property real textWidth: Math.max(0, width - orbSize - 12)
    property real orbCenterY: height / 2
    Native.SpeechOrb {
        objectName: "islandVoiceOrb"
        width: root.orbSize; height: width
        anchors.right: parent.right; y: root.orbCenterY - height / 2
        level: root.level
        active: root.active && (root.phase === "listening" || root.phase === "speaking")
        processing: root.active && (root.phase === "thinking" || root.phase === "transcribing")
        effectsActive: root.active
        reducedMotion: Theme.effectiveReducedMotion
    }
    Label {
        objectName: "islandVoiceHeard"
        x: 0; y: 0; width: root.textWidth; height: root.replying ? 20 : 48
        text: root.replying ? (root.finalTranscript ? "Heard: " + root.finalTranscript : "") : root.recognized || (root.phase === "listening" ? "Listening…" : root.phase === "error" ? "Please try again." : "Transcribing…")
        color: root.replying ? IslandStyle.secondary : IslandStyle.text
        font.pixelSize: root.replying ? 11 : 16; font.weight: root.replying ? Font.Normal : Font.Medium
        wrapMode: Text.Wrap; maximumLineCount: root.replying ? 1 : 2; elide: Text.ElideRight
        Accessible.name: root.finalTranscript ? "Heard: " + root.finalTranscript : "Live transcript: " + root.partialTranscript
    }
    Label {
        objectName: "islandVoiceAnswer"
        x: 0; y: 26; width: root.textWidth; height: 48
        visible: root.replying
        text: root.answer; color: IslandStyle.text; font.pixelSize: 16; font.weight: Font.Medium
        wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
    }
    Label {
        objectName: "islandVoiceFooter"
        anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.right: button.left; height: 28
        text: root.finalTranscript ? "Final transcript" : root.phase === "listening" ? "Live transcript · may change" : root.phase === "transcribing" ? "Finishing transcription" : ""
        color: IslandStyle.secondary; font.pixelSize: 10; elide: Text.ElideRight
    }
    ActionButton {
        id: button
        objectName: "islandVoiceOpen"
        x: root.textWidth - width; anchors.bottom: parent.bottom
        text: "Open Thursday"; quiet: true; textColor: IslandStyle.secondary
        font.pixelSize: 11; width: Math.min(110, root.textWidth); height: 28
        onClicked: root.openRequested()
    }
}
