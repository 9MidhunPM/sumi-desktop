pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQml.Models
import Quickshell
import Quickshell.Hyprland
import Quickshell.Services.SystemTray
import Quickshell.Wayland
import "config"
import "services" as S
import "components" as C
import "CodexStatusModule/StatusFormat.js" as CodexFormat

// Three translucent islands leave the wallpaper visible. Five persistent
// workspaces show one dot per window; occupied extras appear on demand.
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
    readonly property var trayItems: SystemTray.items.values
    readonly property var codexController: app.codexStatus || null
    readonly property var codexWeeklyRemaining: codexController ? CodexFormat.weekly(codexController.usage) : null
    readonly property bool codexQuotaFresh: !!codexController && codexController.usageFresh === true
    readonly property string codexQuotaText: codexWeeklyRemaining === null ? "—"
        : CodexFormat.percent(codexWeeklyRemaining) + (codexQuotaFresh ? "" : " stale")
    readonly property string codexQuotaTooltip: "Codex · Weekly limit remaining: "
        + (codexWeeklyRemaining === null ? "unavailable" : CodexFormat.percent(codexWeeklyRemaining))
        + (codexQuotaFresh ? "" : codexController && codexController.online ? " · stale" : " · offline")
    readonly property int inlineTrayCount: Math.min(trayItems.length, width >= 1800 ? 3 : width >= 1400 ? 1 : 0)
    readonly property real centerRoom: Math.max(0, width - 2 * Math.max(leftIsland.width, rightIsland.width) - (compact ? 32 : 56))
    property int spectrumConsumer: 0
    readonly property bool visualizationWanted: app.barVisible && musicIsland.visible && musicIsland.expanded
    onVisualizationWantedChanged: S.Spectrum.setDemand(spectrumConsumer, visualizationWanted)
    Component.onCompleted: { spectrumConsumer = S.Spectrum.createConsumer(); S.Spectrum.setDemand(spectrumConsumer, visualizationWanted); }
    Component.onDestruction: S.Spectrum.setDemand(spectrumConsumer, false)
    Behavior on reveal {
        NumberAnimation {
            duration: Theme.effectiveReducedMotion ? 0 : Theme.batteryMotion ? (bar.app.barVisible ? 140 : 110) : 180
            easing.type: bar.app.barVisible ? Easing.OutCubic : Easing.InCubic
        }
    }
    onVisibleChanged: if (!visible) { trayMenu.close(); workspaceMenu.close(); }
    Connections {
        target: bar.app
        function onPanelChanged() { if (bar.app.panel !== "") { trayMenu.close(); workspaceMenu.close(); } }
        function onBarVisibleChanged() { if (!bar.app.barVisible) { trayMenu.close(); workspaceMenu.close(); } }
    }
    function activateTray(item, secondary) {
        if ((secondary || item.onlyMenu) && item.hasMenu) item.display(bar, bar.width - rightIsland.width, bar.height + 8);
        else if (!secondary) item.activate();
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
            width: leftRow.implicitWidth + (bar.compact ? 12 : 20)
            height: Theme.barHeight - 2
            Rectangle { anchors.fill: parent; radius: height / 2; color: Theme.barBackground; border.width: 1; border.color: Theme.borderSoft }
            RowLayout {
                id: leftRow
                anchors.centerIn: parent
                spacing: bar.compact ? 1 : 4
                C.ActionButton {
                    objectName: "barLauncher"
                    iconName: "arch"; iconSize: 20
                    text: ""
                    textColor: Theme.accentBlue
                    quiet: true; padding: 8
                    implicitWidth: bar.compact ? 30 : 40
                    implicitHeight: 28
                    tooltip: "Command hub · Super+Space"
                    onClicked: app.toggle("launcher", bar.screen)
                }
                Item { implicitWidth: bar.compact ? 5 : 12; implicitHeight: 24; Rectangle { anchors.centerIn: parent; width: 1; height: 14; color: Theme.borderSoft } }
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
        C.MusicIsland {
            id: musicIsland
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            width: implicitWidth
            height: Theme.barHeight - 2
            compact: bar.width < 760
            playing: S.Media.playing
            expanded: playing && bar.centerRoom >= expandedWidth
            onClockClicked: bar.app.toggle("calendar", bar.screen)
            onMusicClicked: bar.app.toggle("media", bar.screen)
        }
        Item {
            id: rightIsland
            anchors.right: parent.right
            anchors.rightMargin: 0
            anchors.verticalCenter: parent.verticalCenter
            width: rightRow.implicitWidth + (bar.compact ? 12 : 20)
            height: Theme.barHeight - 2
            Rectangle { anchors.fill: parent; radius: height / 2; color: Theme.barBackground; border.width: 1; border.color: Theme.borderSoft }
            RowLayout {
                id: rightRow
                anchors.centerIn: parent
                spacing: 4
                C.ActionButton { objectName: "barThursday"; visible: bar.width >= 1100; iconName: "assistant"; iconSize: 21; quiet: true; padding: 6; implicitWidth: 34; implicitHeight: 28; tooltip: "Thursday · Super+C"; onClicked: app.thursdayToggle() }
                C.ActionButton {
                    objectName: "barCodex"
                    visible: bar.width >= 1100
                    iconName: "codex"; iconSize: 21; iconSpacing: 6
                    text: bar.codexQuotaText
                    textColor: bar.codexQuotaFresh ? Theme.accentBlue : Theme.textSoft
                    quiet: true; padding: 6
                    leftPadding: 8; rightPadding: 8
                    implicitWidth: contentItem.implicitWidth + 16; implicitHeight: 28
                    tooltip: bar.codexQuotaTooltip
                    onClicked: app.codexToggle(bar.screen)
                }
                Item { visible: bar.width >= 1100; implicitWidth: 12; implicitHeight: 24; Rectangle { anchors.centerIn: parent; width: 1; height: 14; color: Theme.borderSoft } }
                Repeater {
                    model: bar.trayItems.slice(0, bar.inlineTrayCount)
                    C.ActionButton {
                        id: trayButton
                        required property var modelData
                        quiet: true; padding: 6
                        implicitWidth: 34; implicitHeight: 28
                        tooltip: modelData.tooltipTitle || modelData.title || "Tray application"
                        onClicked: bar.activateTray(modelData, false)
                        C.Icon { anchors.centerIn: parent; name: "apps"; size: 16; visible: trayImage.status !== Image.Ready; color: Theme.textSoft }
                        Image { id: trayImage; anchors.centerIn: parent; source: trayButton.modelData.icon; width: 16; height: 16; sourceSize: Qt.size(32, 32); fillMode: Image.PreserveAspectFit; visible: status === Image.Ready }
                        TapHandler { acceptedButtons: Qt.RightButton; onTapped: bar.activateTray(trayButton.modelData, true) }
                    }
                }
                C.ActionButton {
                    id: trayOverflow
                    visible: bar.trayItems.length > bar.inlineTrayCount
                    iconName: "more-horizontal"; iconSize: 17
                    quiet: true; padding: 6; implicitWidth: 32; implicitHeight: 28
                    tooltip: "Tray applications"
                    onClicked: trayMenu.popup(trayOverflow, 0, trayOverflow.height + 12)
                }
                C.ActionButton {
                    objectName: "barNotifications"
                    iconName: Settings.dnd ? "bell-off" : "bell"; iconSize: 17
                    quiet: true; padding: 8; implicitWidth: 36; implicitHeight: 28
                    tooltip: "Notifications · Super+N"
                    onClicked: app.toggle("notifications", bar.screen)
                    Rectangle { anchors.right: parent.right; anchors.rightMargin: 6; anchors.top: parent.top; anchors.topMargin: 5; width: 5; height: 5; radius: 3; visible: S.Notifications.unread > 0; color: Theme.accentPink }
                }
                C.ActionButton { visible: bar.width >= 1400; iconName: S.Network.connected ? "wifi" : "wifi-off"; iconSize: 17; quiet: true; padding: 8; implicitWidth: 36; implicitHeight: 28; tooltip: S.Network.name || "Network"; onClicked: app.openSettings("wifi", bar.screen) }
                C.ActionButton {
                    objectName: "barBluetooth"
                    visible: bar.width >= 1600; iconName: S.Bluetooth.enabled ? "bluetooth" : "bluetooth-off"; iconSize: 17; quiet: true; padding: 8; implicitWidth: 34; implicitHeight: 28; textColor: S.Bluetooth.enabled ? Theme.accentCyan : Theme.textSoft
                    tooltip: "Bluetooth · right-click for Bluetooth manager"
                    onClicked: app.openSettings("bluetooth", bar.screen)
                    TapHandler { acceptedButtons: Qt.RightButton; onTapped: { bar.app.close(); S.Bluetooth.openManager(); } }
                }
                C.ActionButton {
                    objectName: "barAudio"
                    visible: bar.width >= 760; iconName: S.Audio.muted ? "volume-x" : "volume"; iconSize: 17; quiet: true; padding: 8; implicitWidth: 36; implicitHeight: 28
                    tooltip: "Audio · " + Math.round(S.Audio.volume * 100) + "% · right-click for sound mixer"
                    onClicked: app.openSettings("audio", bar.screen)
                    TapHandler { acceptedButtons: Qt.RightButton; onTapped: { bar.app.close(); S.Audio.openManager(); } }
                }
                C.ActionButton {
                    id: batteryButton
                    objectName: "barBattery"
                    visible: S.Battery.available && bar.width >= 760
                    text: Math.round(S.Battery.percent) + "%"
                    iconName: S.Battery.charging ? "battery-charging" : "battery"; iconSize: 18
                    textColor: S.Battery.percent < 20 ? Theme.accentWarn : Theme.textMain
                    quiet: true; padding: 8; implicitWidth: batteryWidth.width + iconSize + iconSpacing + 16; implicitHeight: 28
                    leftPadding: 8; rightPadding: 8
                    TextMetrics { id: batteryWidth; font: batteryButton.font; text: "100%" }
                    tooltip: "Battery · " + S.Battery.timeLabel
                    onClicked: app.toggle("settings", bar.screen)
                }
                C.ActionButton { objectName: "barSettings"; iconName: "settings"; iconSize: 17; quiet: true; padding: 8; implicitWidth: 38; implicitHeight: 28; tooltip: "Control center"; onClicked: app.toggle("settings", bar.screen) }
            }
        }
        Menu {
            id: trayMenu
            popupType: Popup.Window
            font.family: Theme.font
            palette.text: Theme.textMain
            palette.windowText: Theme.textMain
            palette.highlight: Theme.bgPlaying
            palette.highlightedText: Theme.textMain
            background: C.Surface {}
            Instantiator {
                model: bar.trayItems.slice(bar.inlineTrayCount)
                delegate: MenuItem {
                    required property var modelData
                    text: modelData.title || modelData.tooltipTitle || "Tray application"
                    icon.source: modelData.icon
                    icon.color: "transparent"
                    onTriggered: bar.activateTray(modelData, false)
                }
                onObjectAdded: (index, object) => trayMenu.insertItem(index, object)
                onObjectRemoved: (index, object) => trayMenu.removeItem(object)
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
