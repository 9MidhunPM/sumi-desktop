pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import "../services" as S

// Keep dismissal visible while long messages and sender actions scroll below it.
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
    implicitHeight: header.implicitHeight + message.implicitHeight + 29
    radius: 21
    color: "#24252b"
    enabled: active && !!entry
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 5
        RowLayout {
            id: header
            Layout.fillWidth: true; Layout.minimumWidth: 0
            spacing: 7
            Rectangle {
                implicitWidth: 23; implicitHeight: 23; radius: 7; color: "#3b3d47"
                Icon { anchors.centerIn: parent; name: "bell"; size: 14; color: "#e2e3eb"; visible: appImage.status !== Image.Ready }
                Image { id: appImage; anchors.fill: parent; source: root.appIcon; sourceSize: Qt.size(46,46); fillMode: Image.PreserveAspectFit; asynchronous: true; visible: status === Image.Ready }
            }
            Label { Layout.fillWidth: true; Layout.minimumWidth: 0; text: root.entry ? root.entry.appName : "Notification"; color: "#bfc1ce"; font.pixelSize: 11; font.weight: Font.Medium }
            Label { text: root.entry && root.entry.time && !isNaN(new Date(root.entry.time).getTime()) ? Qt.formatDateTime(new Date(root.entry.time), "h:mm") : ""; font.pixelSize: 10; color: "#989cac" }
            IslandPreviewButton { text: "›"; tooltip: "Open notification in Inbox"; quiet: true; implicitWidth: 30; implicitHeight: 30; leftPadding: 4; rightPadding: 4; onClicked: root.openRequested() }
            IslandPreviewButton { objectName: "islandNotificationDismiss"; text: "×"; tooltip: "Dismiss notification"; quiet: true; implicitWidth: 30; implicitHeight: 30; leftPadding: 4; rightPadding: 4; onClicked: root.dismissRequested() }
        }
        ScrollView {
            id: scroll
            objectName: "islandNotificationScroll"
            Layout.fillWidth: true; Layout.minimumWidth: 0
            Layout.fillHeight: true; Layout.minimumHeight: 0
            implicitHeight: message.implicitHeight
            clip: true
            contentWidth: availableWidth
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            Column {
                id: message
                width: scroll.availableWidth
                spacing: 5
                Label { width: parent.width; text: root.entry ? root.entry.summary : ""; color: "#f7f7fb"; font.pixelSize: 13; font.weight: Font.DemiBold; wrapMode: Text.Wrap }
                Label { width: parent.width; visible: text.length > 0; text: root.entry ? root.entry.body || "" : ""; color: "#b7bac8"; font.pixelSize: 12; wrapMode: Text.Wrap }
                Flow {
                    width: parent.width
                    visible: !!root.entry && (root.entry.actions || []).length > 0
                    spacing: 6
                    Repeater {
                        model: root.entry ? root.entry.actions || [] : []
                        IslandPreviewButton {
                            required property string modelData
                            required property int index
                            objectName: "islandNotificationAction" + index
                            width: Math.min(implicitWidth, message.width)
                            text: modelData; tooltip: modelData
                            implicitHeight: 30; font.pixelSize: 11
                            onClicked: { if (root.entry) S.Notifications.invoke(root.entry.id, index); }
                            onActiveFocusChanged: {
                                if (!activeFocus) return;
                                const viewport = scroll.contentItem;
                                const point = mapToItem(viewport.contentItem, 0, 0);
                                if (point.y < viewport.contentY) viewport.contentY = point.y;
                                else if (point.y + height > viewport.contentY + viewport.height)
                                    viewport.contentY = Math.max(0, point.y + height - viewport.height);
                            }
                        }
                    }
                }
            }
        }
    }
}
