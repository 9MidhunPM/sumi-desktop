pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import "../config"
import "../integrations" as Native

// Passive response and measured speech orb; no transport or playback ownership.
Item {
    id: root
    property string text: ""
    // Retained for host compatibility; this surface creates no speech bars.
    property var samples: []
    property bool speaking: false
    property real level: 0
    property bool processing: false
    property bool active: false
    readonly property real preferredHeight: 180 + Math.min(260, Math.max(60, Math.ceil(response.contentHeight) + 30))
    implicitHeight: preferredHeight
    visible: active
    enabled: active
    Native.SpeechOrb {
        id: orb
        objectName: "islandAssistantOutputOrb"
        anchors { horizontalCenter: parent.horizontalCenter; top: parent.top }
        width: Math.min(160, root.width); height: Math.min(160, Math.max(0, root.height - 60))
        active: root.active && visible && (root.speaking || root.processing)
        effectsActive: root.active && visible
        level: root.level
        processing: root.processing
        reducedMotion: Theme.effectiveReducedMotion
    }
    Label {
        id: sender
        objectName: "islandAssistantOutputSender"
        anchors { left: parent.left; right: parent.right; top: orb.bottom; topMargin: 12 }
        height: 22
        text: "Thursday:"
        font.pixelSize: 11
        font.weight: Font.DemiBold
        color: "#b9bcca"
        Accessible.name: "Thursday says"
    }
    ScrollView {
        id: viewport
        objectName: "islandAssistantOutputScroll"
        anchors { left: parent.left; right: parent.right; top: sender.bottom; topMargin: 4; bottom: parent.bottom }
        contentWidth: availableWidth
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical.policy: ScrollBar.AsNeeded
        TextEdit {
            id: response
            objectName: "islandAssistantOutputText"
            width: Math.max(1, root.width - 10)
            text: root.text
            font.family: Theme.font
            font.pixelSize: 14
            color: "#f4f4f7"
            textFormat: TextEdit.PlainText
            wrapMode: TextEdit.Wrap
            readOnly: true
            selectByMouse: true
            activeFocusOnTab: false
            selectionColor: "#d7d8e0"
            selectedTextColor: "#17181d"
            padding: 0
            Accessible.role: Accessible.StaticText
            Accessible.name: "Thursday: " + root.text
        }
    }
}
