pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import "../services" as S

// A compact native notification card; the host owns focus and deadlines.
Rectangle {
    id: root
    property var entry: null
    property bool active: true
    readonly property string appIcon: {
        const name = entry ? String(entry.appIcon || "") : "";
        if (!name) return "";
        return /^(file:|image:|\/)/.test(name) ? name : Quickshell.iconPath(name, true) || "";
    }
    signal openRequested()
    signal dismissRequested()
    implicitHeight: content.implicitHeight + 24
    radius: 21
    color: "#24252b"
    enabled: active && !!entry
    ColumnLayout {
        id: content
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
        spacing: 5
        RowLayout {
            Layout.fillWidth: true; Layout.minimumWidth: 0
            spacing: 7
            Rectangle {
                implicitWidth: 23; implicitHeight: 23; radius: 7; color: "#3b3d47"
                Icon { anchors.centerIn: parent; name: "bell"; size: 14; color: "#e2e3eb"; visible: appImage.status !== Image.Ready }
                Image { id: appImage; anchors.fill: parent; source: root.appIcon; sourceSize: Qt.size(46,46); fillMode: Image.PreserveAspectFit; asynchronous: true; visible: status === Image.Ready }
            }
            Label { Layout.fillWidth: true; Layout.minimumWidth: 0; text: root.entry ? root.entry.appName : "Notification"; color: "#bfc1ce"; font.pixelSize: 11; font.weight: Font.Medium }
            Label { visible: !!root.entry && root.entry.unread === true; text: "●"; color: "#f4f4f8"; font.pixelSize: 7; Accessible.name: "Unread" }
            Label { text: root.entry && root.entry.time && !isNaN(new Date(root.entry.time).getTime()) ? Qt.formatDateTime(new Date(root.entry.time), "h:mm") : ""; font.pixelSize: 10; color: "#989cac" }
            IslandPreviewButton { text: "›"; tooltip: "Open notification in Inbox"; quiet: true; implicitWidth: 25; implicitHeight: 25; leftPadding: 4; rightPadding: 4; onClicked: root.openRequested() }
            IslandPreviewButton { text: "×"; tooltip: "Dismiss notification"; quiet: true; implicitWidth: 25; implicitHeight: 25; leftPadding: 4; rightPadding: 4; onClicked: root.dismissRequested() }
        }
        Label { Layout.fillWidth: true; Layout.minimumWidth: 0; text: root.entry ? root.entry.summary : ""; color: "#f7f7fb"; font.pixelSize: 13; font.weight: Font.DemiBold; wrapMode: Text.Wrap; maximumLineCount: 2 }
        Label { Layout.fillWidth: true; Layout.minimumWidth: 0; visible: text.length > 0; text: root.entry ? root.entry.body || "" : ""; color: "#b7bac8"; font.pixelSize: 12; wrapMode: Text.Wrap; maximumLineCount: 2 }
        RowLayout {
            Layout.fillWidth: true; Layout.minimumWidth: 0
            visible: !!root.entry && (root.entry.actions || []).length > 0
            spacing: 6
            Repeater {
                model: root.entry ? (root.entry.actions || []).slice(0, 2) : []
                IslandPreviewButton {
                    required property string modelData
                    required property int index
                    Layout.fillWidth: true; Layout.minimumWidth: 0
                    text: modelData; implicitHeight: 29; font.pixelSize: 11
                    onClicked: { if (root.entry) S.Notifications.invoke(root.entry.id, index); }
                }
            }
        }
    }
}
