pragma ComponentBehavior: Bound
import QtQuick
import "../services" as S

Item {
    id: root
    required property var app
    property double now: Date.now()
    readonly property bool wide: width >= 460
    readonly property real unit: wide ? (width - 24) / 3 : (width - 12) / 2
    implicitHeight: wide ? 126 : 210
    signal controlsRequested()
    signal captureRequested()
    signal recordingRequested()
    function duration() {
        const seconds = Math.max(0, Math.ceil((app.focusRunning ? app.focusDeadline - now : app.focusRemaining) / 1000));
        return Math.floor(seconds/60) + ":" + String(seconds%60).padStart(2,"0");
    }
    Rectangle {
        width: root.wide ? root.unit : root.width
        height: root.wide ? 126 : 74
        radius: 24
        color: "#24252b"
        Icon { x: parent.width - 42; y: 16; name: S.Battery.charging ? "battery-charging" : "battery"; size: 23; color: "#c9cbd5" }
        Label { x: 16; y: root.wide ? 18 : 9; text: S.Battery.available ? Math.round(S.Battery.percent) + "%" : "AC power"; font.pixelSize: root.wide ? 28 : 23; font.weight: Font.DemiBold; color: "#f7f7fa" }
        Label { x: 16; y: root.wide ? 57 : 40; width: parent.width - 32; text: S.Battery.timeLabel; font.pixelSize: 11; color: "#b8bac6" }
        Rectangle { x: 16; y: 98; width: parent.width - 32; height: 5; radius: 3; visible: root.wide; color: "#484952"; Rectangle { width: parent.width * S.Battery.percent/100; height: 5; radius: 3; color: "#f4f4f8" } }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.controlsRequested() }
    }
    IslandControlTile {
        objectName: "islandDashboardFocus"
        x: root.wide ? root.unit + 12 : 0
        y: root.wide ? 0 : 86
        width: root.unit; height: 124
        iconName: "moon"; title: "Focus"; subtitle: root.app.focusRunning ? root.duration() + " remaining" : "Ready · " + root.duration()
        selected: root.app.focusRunning; activeColor: "#534179"; glyphColor: "#cab3ff"
        onClicked: { if (root.app.focusRunning) root.app.focusPause(); else root.app.focusStart(); }
        IslandPreviewButton { anchors { right: parent.right; top: parent.top; margins: 8 } text: "Reset"; font.pixelSize: 10; implicitHeight: 28; quiet: true; onClicked: root.app.focusReset(25) }
    }
    IslandControlTile {
        objectName: "islandHomeRecord"
        x: root.wide ? (root.unit + 12) * 2 : root.unit + 12
        y: root.wide ? 0 : 86
        width: root.unit; height: 124
        iconName: S.Recording.recording ? "stop" : "record"; title: S.Recording.recording ? "Stop recording" : "Record region"; subtitle: S.Recording.recording ? "Recording in progress" : "Capture your screen"
        glyphColor: S.Recording.recording ? "#ff7c83" : "#f4f4f8"
        enabled: S.Recording.ready && !S.Recording.busy
        onClicked: { if (S.Recording.recording) S.Recording.stop(); else root.recordingRequested(); }
        IslandPreviewButton { anchors { right: parent.right; top: parent.top; margins: 8 } text: "Capture"; font.pixelSize: 10; implicitHeight: 28; quiet: true; onClicked: root.captureRequested() }
    }
}
