pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import "../config"

// Passive response only. Speech visualization belongs to the island header.
Item {
    id: root
    property string text: ""
    // Retained for host compatibility; this surface creates no speech bars.
    property var samples: []
    property bool speaking: false
    property bool active: false
    readonly property real preferredHeight: Math.min(260, Math.max(60, Math.ceil(response.contentHeight) + 30))
    implicitHeight: preferredHeight
    visible: active
    enabled: active
    Label {
        id: sender
        objectName: "islandAssistantOutputSender"
        anchors { left: parent.left; right: parent.right; top: parent.top }
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
