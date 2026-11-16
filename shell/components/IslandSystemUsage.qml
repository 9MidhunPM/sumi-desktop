pragma ComponentBehavior: Bound
import QtQuick
import "../config"
import "../services" as S

Rectangle {
    id: root
    objectName: "islandUsage-" + metric
    property string metric: "cpu"
    readonly property bool available: metric === "cpu" ? S.SystemStats.cpuAvailable : metric === "memory" ? S.SystemStats.memoryAvailable : S.SystemStats.storageAvailable
    readonly property real percent: metric === "cpu" ? S.SystemStats.cpuPercent : metric === "memory" ? S.SystemStats.memoryPercent : S.SystemStats.storagePercent
    readonly property real used: metric === "memory" ? S.SystemStats.memoryUsed : S.SystemStats.storageUsed
    readonly property real total: metric === "memory" ? S.SystemStats.memoryTotal : S.SystemStats.storageTotal
    readonly property string title: metric === "cpu" ? "CPU" : metric === "memory" ? "RAM" : "Storage"
    // Before the first sample arrives the value is still being measured, not missing.
    readonly property bool pending: !available && S.SystemStats.receivedSample === false && !S.SystemStats.error
    readonly property string valueText: pending ? "—" : !available ? "Unavailable" : metric === "cpu" ? Math.round(percent) + "%" : bytes(used)
    signal activated()
    implicitHeight: 82
    radius: 18
    color: pointer.containsMouse ? Qt.lighter(IslandStyle.raised, 1.25) : IslandStyle.raised
    Behavior on color { ColorAnimation { duration: Motion.control } }
    // A pointer shortcut to the detailed System page; the values stay readable as text.
    MouseArea { id: pointer; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.activated() }
    function bytes(value) {
        const gib = Math.max(0, value) / 1073741824;
        return (gib < 10 ? gib.toFixed(1) : Math.round(gib)) + " GB";
    }
    Accessible.role: Accessible.StaticText
    Accessible.name: title + ": " + valueText + (available && metric !== "cpu" ? " of " + bytes(total) : "")
    Label { x: 14; y: 10; width: parent.width - 28; text: root.title; font.pixelSize: IslandStyle.captionText; font.weight: Font.Medium; color: IslandStyle.secondary }
    Label { objectName: "islandUsageValue-" + root.metric; x: 14; y: 26; width: parent.width - 28; text: root.valueText; font.pixelSize: root.available || root.pending ? 22 : 13; font.weight: Font.DemiBold; font.features: IslandStyle.figures; color: root.pending ? IslandStyle.secondary : IslandStyle.text }
    Label { x: 14; y: 53; width: parent.width - 28; text: root.pending ? "Measuring…" : !root.available ? "Check system access" : root.metric === "cpu" ? "Current load" : "of " + root.bytes(root.total); font.pixelSize: IslandStyle.captionText; color: IslandStyle.secondary }
    Rectangle {
        x: 14; y: 70; width: parent.width - 28; height: 3; radius: 2; color: "#3a3a40"; visible: root.available || root.pending
        Rectangle {
            width: parent.width * (root.available ? Math.max(0, Math.min(100, root.percent)) / 100 : 0); height: 3; radius: 2; color: "#d9dce8"
            Behavior on width { NumberAnimation { duration: Motion.reveal; easing.type: Easing.OutCubic } }
        }
    }
}
