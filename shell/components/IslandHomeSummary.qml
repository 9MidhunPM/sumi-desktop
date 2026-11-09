pragma ComponentBehavior: Bound
import QtQuick
import "../services" as S

Item {
    id: root
    required property var app
    property double now: Date.now()
    readonly property bool wide: width >= 390
    readonly property real unit: wide ? (width - 24) / 3 : (width - 12) / 2
    readonly property real usageHeight: wide ? 82 : 176
    implicitHeight: usageHeight + 120
    IslandPreviewButton {
        id: calendarButton
        objectName: "islandHomeCalendar"
        y: root.usageHeight + 82
        width: root.width; height: 38
        iconName: "calendar"; iconSize: 16
        text: "Calendar"; tooltip: "Open calendar in island"
        onClicked: root.calendarRequested()
    }
    signal calendarRequested()
    signal controlsRequested()
    signal captureRequested()
    signal recordingRequested()
    IslandSystemUsage { x: 0; width: root.unit; height: 82; metric: "cpu" }
    IslandSystemUsage { x: root.unit + 12; width: root.unit; height: 82; metric: "memory" }
    IslandSystemUsage { x: root.wide ? (root.unit + 12) * 2 : 0; y: root.wide ? 0 : 94; width: root.wide ? root.unit : root.width; height: 82; metric: "storage" }
    Rectangle {
        y: root.usageHeight + 12
        width: root.width; height: 60
        radius: 21; color: "#202126"
        Icon { x: 15; anchors.verticalCenter: parent.verticalCenter; name: S.Battery.charging ? "battery-charging" : "battery"; size: 22; color: "#c5cbd9" }
        Label { x: 47; y: 12; width: parent.width - 94; text: S.Battery.available ? Math.round(S.Battery.percent) + "% battery" : "AC power"; font.pixelSize: 12; font.weight: Font.DemiBold; color: "#f2f4fa" }
        Label { x: 47; y: 31; width: parent.width - 94; text: S.Battery.timeLabel; font.pixelSize: 10; color: "#a7afc2" }
        IslandPreviewButton { anchors { right: parent.right; verticalCenter: parent.verticalCenter; rightMargin: 9 } text: "›"; tooltip: "Power and system controls"; quiet: true; implicitWidth: 32; onClicked: root.controlsRequested() }
    }
}
