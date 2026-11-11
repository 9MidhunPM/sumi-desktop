pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as Shell
import "../config"
import "../services" as S

FocusScope {
    id: root
    required property var app
    property string route: "controls"
    property bool active: false
    property double now: Date.now()
    property var spectrumSamples: []
    readonly property real contentHeight: deviceRoute ? settings.contentHeight
        : route === "power" || route === "pomodoro" ? dashboard.contentHeight : overviewContent.implicitHeight
    signal routeRequested(string route)
    signal captureRequested(bool annotate)
    signal recordingRequested()
    readonly property bool deviceRoute: ["wifi", "bluetooth", "audio", "capture"].indexOf(route) >= 0
    readonly property var assistant: typeof app.thursdayBackend === "undefined" ? null : app.thursdayBackend
    readonly property string assistantStatus: !assistant ? "Ask Thursday" : assistant.confirmations && assistant.confirmations.length ? "Thursday · Approval needed" : assistant.recording ? "Thursday · Listening" : assistant.busy || assistant.taskActive ? "Thursday · Working…" : assistant.speaking ? "Thursday · Speaking" : "Ask Thursday"
    property int statsConsumer: 0
    function syncDemand() { if (statsConsumer) S.SystemStats.setDemand(statsConsumer, active && route === "system"); }
    Component.onCompleted: { statsConsumer = S.SystemStats.createConsumer(); syncDemand(); }
    Component.onDestruction: if (statsConsumer) S.SystemStats.releaseConsumer(statsConsumer)
    onActiveChanged: syncDemand()
    onRouteChanged: syncDemand()
    function focusDefault() { if (deviceRoute) settings.focusDefault(); else if (dashboard.visible) dashboard.focusDefault(); else overview.forceActiveFocus(Qt.OtherFocusReason); }
    function back() { return deviceRoute ? settings.back() : false; }
    component Caption: Label { color: IslandStyle.secondary; font.family: Theme.font; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
    component Heading: Label { color: IslandStyle.text; font.family: Theme.font; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true; topPadding: 12 }
    component RouteRow: Button {
        id: row
        property string iconName: "settings"
        property string detail: ""
        property string target: ""
        Layout.fillWidth: true
        implicitHeight: 62
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: text + (detail ? ", " + detail : "")
        onClicked: root.routeRequested(target)
        background: Rectangle { radius: 12; color: row.down || row.hovered ? IslandStyle.hover : "transparent"; border.width: row.visualFocus ? 2 : 0; border.color: Theme.accentCyan }
        contentItem: RowLayout {
            spacing: 14
            Icon { name: row.iconName; size: 22; color: IslandStyle.text; Layout.leftMargin: 10 }
            ColumnLayout {
                spacing: 3; Layout.fillWidth: true
                Label { text: row.text; color: IslandStyle.text; font.family: Theme.font; font.pixelSize: 14; font.weight: Font.Medium }
                Label { text: row.detail; visible: text.length > 0; color: IslandStyle.secondary; font.family: Theme.font; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
            }
            Icon { name: "arrow-right"; size: 16; color: IslandStyle.secondary; Layout.rightMargin: 10 }
        }
    }
    ScrollView {
        id: overview
        anchors.fill: parent
        visible: !root.deviceRoute && !dashboard.visible
        enabled: visible && root.active
        clip: true
        contentWidth: availableWidth
        ColumnLayout {
            id: overviewContent
            width: overview.availableWidth
            spacing: 6
            ColumnLayout {
                visible: root.route === "controls"
                Layout.fillWidth: true; spacing: 12
                IslandControlCenter {
                    Layout.fillWidth: true
                    Layout.preferredHeight: implicitHeight
                    app: root.app; active: root.active && root.route === "controls"; now: root.now
                    spectrumSamples: root.spectrumSamples
                    onSettingsRequested: section => root.routeRequested(section)
                    onCaptureRequested: annotate => root.captureRequested(annotate)
                    onRecordingRequested: root.recordingRequested()
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: width >= 500 ? 6 : 4
                    rowSpacing: 4; columnSpacing: 4
                    Repeater {
                        model: [{label:"Search",route:"launcher",icon:"search"},{label:"Clipboard",route:"clipboard",icon:"clipboard"},{label:"Appearance",route:"appearance",icon:"palette"},{label:"Capture",route:"capture",icon:"camera"},{label:"Focus",route:"pomodoro",icon:"timer"},{label:"Widgets",route:"widgets",icon:"layout-grid"},{label:"System",route:"system",icon:"cpu"},{label:"Sound",route:"audio",icon:"volume"},{label:"Calendar",route:"calendar",icon:"calendar"},{label:"Files",route:"files",icon:"folder"},{label:"Codex",route:"codex",icon:"terminal"},{label:"Power",route:"power",icon:"power"}]
                        Button {
                            id: tool
                            required property var modelData
                            objectName: "islandTool-" + modelData.route
                            Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 0
                            implicitHeight: 58
                            hoverEnabled: true; focusPolicy: Qt.StrongFocus
                            Accessible.name: modelData.label
                            background: Rectangle { radius: 12; color: tool.hovered || tool.down ? IslandStyle.hover : "transparent"; border.width: tool.visualFocus ? 2 : 0; border.color: IslandStyle.text }
                            contentItem: Item {
                                Icon { anchors.horizontalCenter: parent.horizontalCenter; y: 4; name: tool.modelData.icon; size: 20; color: IslandStyle.text }
                                Label { anchors { left: parent.left; right: parent.right; bottom: parent.bottom; bottomMargin: 4 } text: tool.modelData.label; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 10; color: IslandStyle.secondary; elide: Text.ElideRight }
                            }
                            onClicked: root.routeRequested(modelData.route)
                        }
                    }
                }
                IslandPreviewButton {
                    objectName: "islandQuickThursday"
                    Layout.fillWidth: true
                    implicitHeight: 48
                    text: root.assistantStatus
                    tooltip: "Open Thursday conversation"
                    iconName: "sparkles"
                    onClicked: root.routeRequested("thursday")
                }
                RowLayout {
                    visible: S.Notifications.count > 0
                    Layout.fillWidth: true
                    Label { text: "Recent notifications"; color: IslandStyle.secondary; font.pixelSize: 12; Layout.fillWidth: true }
                    IslandPreviewButton { text: "Inbox ›"; quiet: true; implicitHeight: 30; onClicked: root.routeRequested("inbox") }
                }
                Repeater {
                    model: S.Notifications.history.slice(0, 2)
                    IslandNotificationPreview {
                        required property var modelData
                        objectName: "islandQuickNotification"
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.min(120, implicitHeight)
                        entry: modelData
                        active: root.active && root.route === "controls"
                        onOpenRequested: {
                            if (typeof root.app.islandSession !== "undefined" && root.app.islandSession) root.app.islandSession.entityId = modelData.id;
                            root.routeRequested("notification");
                        }
                        onDismissRequested: S.Notifications.dismiss(modelData.id)
                    }
                }
                Caption { visible: !!(S.Brightness.error || S.NightLight.error || S.Recording.error); text: S.Brightness.error || S.NightLight.error || S.Recording.error; color: Theme.accentWarn }
            }
            Heading { visible: root.route !== "controls"; text: root.route === "system" ? "System usage" : "Island preferences" }
            ColumnLayout {
                visible: root.route === "system"
                Layout.fillWidth: true; spacing: 12
                IslandSystemUsage { Layout.fillWidth: true; Layout.preferredHeight: 90; metric: "cpu" }
                IslandSystemUsage { Layout.fillWidth: true; Layout.preferredHeight: 90; metric: "memory" }
                IslandSystemUsage { Layout.fillWidth: true; Layout.preferredHeight: 90; metric: "storage" }
                Caption { text: "Usage refreshes while this page is visible." }
            }
            ColumnLayout {
                visible: root.route === "settings"
                Layout.fillWidth: true; spacing: 12
                QuickButton { text: Settings.islandNotch ? "Island: screen-edge notch" : "Island: floating"; Layout.fillWidth: true; onClicked: Settings.setValue("islandNotch", !Settings.islandNotch) }
                QuickButton { text: Settings.reducedMotion ? "Motion: reduced" : Settings.fullMotion ? "Motion: expressive" : "Motion: adaptive"; Layout.fillWidth: true; onClicked: Settings.cycleMotion() }
                QuickButton { text: Settings.dnd ? "Notifications: silenced" : "Notifications: allowed"; Layout.fillWidth: true; onClicked: S.Notifications.toggleDnd() }
                RouteRow { text: "Appearance"; target: "appearance"; detail: "Wallpaper, colors and desktop style" }
                RouteRow { text: "Desktop widgets"; target: "widgets"; detail: "Priorities, deadlines and layout" }
                RouteRow { text: "Keyboard shortcuts"; target: "help"; detail: "Find your desktop shortcuts" }
            }
        }
    }
    Shell.QuickSettings {
        id: settings
        anchors.fill: parent
        app: root.app; embedded: true; pageActive: root.active && root.deviceRoute
        section: root.deviceRoute ? root.route : ""
        visible: root.deviceRoute; enabled: visible && root.active
    }
    Shell.Dashboard {
        id: dashboard
        anchors.fill: parent
        app: root.app; embedded: true; pageActive: root.active && visible
        kind: root.route === "power" ? "power" : "pomodoro"
        visible: root.route === "power" || root.route === "pomodoro"
        enabled: visible && root.active
    }
}
