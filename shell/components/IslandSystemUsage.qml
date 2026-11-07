pragma ComponentBehavior: Bound
import QtQuick
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
    readonly property string valueText: !available ? "Unavailable" : metric === "cpu" ? Math.round(percent) + "%" : bytes(used)
    implicitHeight: 82
    radius: 22
    color: "#24252b"
    function bytes(value) {
        const gib = Math.max(0, value) / 1073741824;
        return (gib < 10 ? gib.toFixed(1) : Math.round(gib)) + " GB";
    }
    Accessible.role: Accessible.StaticText
    Accessible.name: title + ": " + valueText + (available && metric !== "cpu" ? " of " + bytes(total) : "")
    Label { x: 14; y: 10; width: parent.width - 28; text: root.title; font.pixelSize: 10; font.weight: Font.Medium; color: "#aeb3c3" }
    Label { objectName: "islandUsageValue-" + root.metric; x: 14; y: 26; width: parent.width - 28; text: root.valueText; font.pixelSize: root.available ? 22 : 12; font.weight: Font.DemiBold; color: "#f4f5fa" }
    Label { x: 14; y: 53; width: parent.width - 28; text: !root.available ? "Check system access" : root.metric === "cpu" ? "Current load" : "of " + root.bytes(root.total); font.pixelSize: 10; color: "#a7adbe" }
    Rectangle { x: 14; y: 70; width: parent.width - 28; height: 3; radius: 2; color: "#464a55"; visible: root.available; Rectangle { width: parent.width * Math.max(0,Math.min(100,root.percent))/100; height: 3; radius: 2; color: "#d9dce8" } }
}
