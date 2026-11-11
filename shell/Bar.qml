pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQml.Models
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import "config"
import "services" as S
import "components" as C

// Quiet glass side controls frame the separate black dynamic island.
PanelWindow {
    id: bar
    required property var modelData
    required property var app
    screen: modelData
    color: "transparent"
    property real reveal: app.barVisible ? 1 : 0
    visible: app.barVisible || reveal > 0.001
    anchors { top: true; left: true; right: true }
    margins { top: 6; left: 16; right: 16 }
    implicitHeight: Theme.barHeight
    exclusiveZone: Quickshell.env("SUMI_PREVIEW") === "1" || !visible ? 0 : Theme.barHeight - 2
    WlrLayershell.namespace: "sumi-bar"
    WlrLayershell.layer: WlrLayer.Top
    readonly property bool compact: width < 760
    readonly property var monitor: Hyprland.monitors.values.find(candidate => candidate && bar.modelData && candidate.name === bar.modelData.name) || null
    readonly property int activeWorkspaceId: monitor && monitor.activeWorkspace ? monitor.activeWorkspace.id : 0
    readonly property var workspaces: Hyprland.workspaces.values
    readonly property int extraWorkspaceLimit: width >= 1800 ? 6 : width >= 1400 ? 3 : width >= 1100 ? 1 : 0
    readonly property var workspaceEntries: {
        const all = bar.workspaces;
        return Array.from({length: 5}, (_, index) => bar.workspaceEntry(all.find(w => w && w.id === index + 1), index + 1));
    }
    readonly property var additionalWorkspaces: bar.workspaces.filter(workspace =>
        workspace && workspace.id > 5 && workspace.toplevels && (workspace.toplevels.values || []).some(window => !!window))
        .sort((a, b) => a.id - b.id).map(workspace => bar.workspaceEntry(workspace, workspace.id))
    readonly property var inlineExtraWorkspaces: additionalWorkspaces.filter(w => w.id > 5).slice(0, extraWorkspaceLimit)
    readonly property var workspaceMenuEntries: additionalWorkspaces.filter(w => !inlineExtraWorkspaces.some(visible => visible.id === w.id))
    function workspaceEntry(workspace, id) {
        const windows = workspace && workspace.toplevels ? (workspace.toplevels.values || []).filter(w => !!w) : [];
        return {id: id, name: workspace && workspace.name ? workspace.name.replace(/^special:/, "") : String(id),
            target: workspace && workspace.name && workspace.name.startsWith("special:") ? workspace.name : id,
            active: bar.activeWorkspaceId === id, occupied: windows.length > 0, urgent: !!workspace && workspace.urgent === true,
            windowCount: windows.length};
    }
    readonly property real centerRoom: Math.max(0, width - 2 * Math.max(leftIsland.width, rightIsland.width) - (compact ? 32 : 56))
    mask: Region {
        Region { x: leftIsland.x; y: leftIsland.y; width: bar.app.barVisible ? leftIsland.width : 0; height: leftIsland.height }
        Region { x: rightIsland.x; y: rightIsland.y; width: bar.app.barVisible ? rightIsland.width : 0; height: rightIsland.height }
    }
    DynamicIsland {
        id: centerIsland
        modelData: bar.modelData
        app: bar.app
        centerRoom: bar.centerRoom
    }
    Behavior on reveal {
        NumberAnimation {
            duration: bar.app.barVisible ? Theme.motionEnter : Theme.motionExit
            easing.type: bar.app.barVisible ? Easing.OutCubic : Easing.InCubic
        }
    }
    onVisibleChanged: if (!visible) workspaceMenu.close()
    Connections {
        target: bar.app
        function onPanelChanged() { if (bar.app.panel !== "") workspaceMenu.close(); }
        function onBarVisibleChanged() { if (!bar.app.barVisible) workspaceMenu.close(); }
    }

    Item {
        objectName: "barContent"
        anchors.fill: parent
        opacity: bar.reveal
        enabled: bar.app.barVisible
        transform: Translate { y: Theme.effectiveReducedMotion ? 0 : (bar.reveal - 1) * (Theme.barHeight + 6) }
        Item {
            id: leftIsland
            anchors.left: parent.left
            anchors.leftMargin: 0
            anchors.verticalCenter: parent.verticalCenter
            width: leftRow.implicitWidth + (bar.compact ? 12 : 16)
            height: Theme.barHeight - 2
            C.Surface { anchors.fill: parent; radius: IslandStyle.controlRadius; color: Theme.barBackground }
            RowLayout {
                id: leftRow
                anchors.centerIn: parent
                spacing: 2
                Repeater {
                    model: 5
                    C.WorkspaceButton {
                        required property int index
                        entry: bar.workspaceEntries[index]
                        tight: bar.compact
                        onClicked: S.HyprlandActions.focusWorkspace(entry.target)
                    }
                }
                Repeater {
                    model: bar.inlineExtraWorkspaces
                    C.WorkspaceButton {
                        required property var modelData
                        entry: modelData
                        onClicked: S.HyprlandActions.focusWorkspace(entry.target)
                    }
                }
                C.ActionButton {
                    id: extraWorkspaces
                    objectName: "workspaceOverflow"
                    visible: bar.workspaceMenuEntries.length > 0
                    iconName: "more-horizontal"; iconSize: 18
                    quiet: true; padding: 2; implicitWidth: bar.compact ? 26 : 34; implicitHeight: 28
                    tooltip: "More occupied workspaces: " + bar.workspaceMenuEntries.map(workspace => workspace.name).join(", ")
                    onClicked: workspaceMenu.popup(extraWorkspaces, 0, extraWorkspaces.height + 12)
                }
            }
        }
        Item {
            id: rightIsland
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: rightRow.implicitWidth + 12
            height: Theme.barHeight - 2
            C.Surface { anchors.fill: parent; radius: IslandStyle.controlRadius; color: Theme.barBackground }
            RowLayout {
                id: rightRow
                anchors.centerIn: parent
                spacing: 2
                C.ActionButton {
                    objectName: "barAudio"
                    iconName: S.Audio.muted ? "volume-x" : "volume"; iconSize: 16
                    quiet: true; padding: 6; implicitWidth: 28; implicitHeight: 28
                    tooltip: "Audio · " + Math.round(S.Audio.volume * 100) + "% · right-click for sound mixer"
                    onClicked: app.openSettings("audio", bar.screen)
                    TapHandler { acceptedButtons: Qt.RightButton; onTapped: { bar.app.close(); S.Audio.openManager(); } }
                }
                C.ActionButton {
                    objectName: "barWifi"
                    iconName: S.Network.connected ? "wifi" : "wifi-off"; iconSize: 16
                    quiet: true; padding: 6; implicitWidth: 28; implicitHeight: 28
                    tooltip: S.Network.name || "Wi-Fi"
                    onClicked: app.openSettings("wifi", bar.screen)
                }
                C.ActionButton {
                    id: batteryButton
                    objectName: "barBattery"
                    visible: S.Battery.available
                    text: Math.round(S.Battery.percent) + "%"
                    iconName: S.Battery.charging ? "battery-charging" : "battery"; iconSize: 16
                    iconSpacing: 5
                    textColor: S.Battery.percent < 20 ? Theme.accentWarn : Theme.textMain
                    quiet: true; padding: 6; implicitWidth: Math.ceil(batteryWidth.advanceWidth) + iconSize + iconSpacing + 12; implicitHeight: 28
                    leftPadding: 6; rightPadding: 6
                    TextMetrics { id: batteryWidth; font: batteryButton.font; text: "100%" }
                    tooltip: "Battery · " + Math.round(S.Battery.percent) + "% · " + S.Battery.timeLabel
                    onClicked: app.openIsland("controls", bar.screen, true)
                }
                C.ActionButton {
                    objectName: "barSettings"
                    iconName: "settings"; iconSize: 16
                    quiet: true; padding: 6; implicitWidth: 28; implicitHeight: 28
                    tooltip: "Control center"
                    onClicked: app.toggle("settings", bar.screen)
                }
            }
        }
        Menu {
            id: workspaceMenu
            popupType: Popup.Window
            font.family: Theme.font
            palette.text: Theme.textMain
            palette.windowText: Theme.textMain
            palette.highlight: Theme.bgPlaying
            palette.highlightedText: Theme.textMain
            background: C.Surface {}
            Instantiator {
                model: bar.workspaceMenuEntries
                delegate: MenuItem {
                    required property var modelData
                    text: modelData.name
                    checkable: true
                    checked: modelData.active
                    onTriggered: S.HyprlandActions.focusWorkspace(modelData.target)
                }
                onObjectAdded: (index, object) => workspaceMenu.insertItem(index, object)
                onObjectRemoved: (index, object) => workspaceMenu.removeItem(object)
            }
        }
    }
}
