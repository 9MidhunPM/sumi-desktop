pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"
import "IslandSizing.js" as Sizing

// A contextual island workspace: tools replace the work area without tab navigation.
FocusScope {
    id: root
    required property var app
    property var screenInfo: null
    property string section: "controls"
    property bool active: false
    property bool headerEmbedded: false
    property double now: Date.now()
    property real mediaPosition: 0
    property var spectrumSamples: []
    readonly property var sizeProfile: Sizing.profile(resolvedRoute)
    readonly property real preferredWidth: measurementReady && typeof currentPage.preferredWidthHint === "number" && currentPage.preferredWidthHint > 0 ? currentPage.preferredWidthHint : sizeProfile.width
    readonly property bool measurementReady: !!currentPage && (typeof currentPage.route === "undefined" || currentPage.route === resolvedRoute)
    readonly property real naturalPageHeight: currentPage && typeof currentPage.contentHeight === "number" ? currentPage.contentHeight : 220
    // Includes native clock and content insets, then removes them for this Item.
    readonly property real preferredHeight: Sizing.height(sizeProfile, naturalPageHeight, headerEmbedded ? 66 : 118) - 66
    readonly property bool compact: width < 520
    readonly property string resolvedRoute: section === "home" ? "controls" : section === "desktop" ? "launcher" : section
    readonly property string family: familyFor(resolvedRoute)
    readonly property var currentPage: pageFor(family)
    readonly property bool launcherReady: !!pageFor("desktop") && (typeof pageFor("desktop").ready === "undefined" || pageFor("desktop").ready)
    property string pendingPrepare: ""
    property bool pendingFresh: false
    signal sectionRequested(string section)
    signal dismissRequested()
    signal openPanelRequested(string panel)
    signal settingsRequested(string section)
    signal captureRequested(bool annotate)
    signal recordingRequested()
    signal thursdayFullChatRequested()
    enabled: active

    function familyFor(route) {
        if (route === "thursday") return "thursday";
        if (["launcher","files","clipboard","appearance","widgets","codex","help"].indexOf(route) >= 0) return "desktop";
        if (["controls","wifi","bluetooth","audio","capture","system","power","settings","pomodoro"].indexOf(route) >= 0) return "controls";
        return "core";
    }
    function pageFor(name) {
        for (let i = 0; i < pages.count; i++) { const loader = pages.itemAt(i); if (loader && loader.modelData === name) return loader.item; }
        return null;
    }
    function syncPages() {
        for (let i = 0; i < pages.count; i++) {
            const loader = pages.itemAt(i); if (!loader) continue; const page = loader.item;
            if (!page) continue;
            if (loader.modelData === family && typeof page.route !== "undefined") page.route = resolvedRoute;
            if (typeof page.active !== "undefined") page.active = active && loader.modelData === family;
        }
    }
    function focusDefault() {
        if (currentPage && typeof currentPage.focusDefault === "function") currentPage.focusDefault();
        else searchButton.forceActiveFocus(Qt.OtherFocusReason);
    }
    function back() {
        if (currentPage && typeof currentPage.back === "function" && currentPage.back()) return true;
        return typeof app.islandSession !== "undefined" && app.islandSession ? app.islandSession.back() : false;
    }
    function prepare(route, fresh) {
        if (route === "desktop") route = "launcher";
        pendingPrepare = route;
        pendingFresh = fresh;
        const desktop = pageFor("desktop");
        if (desktop && typeof desktop.prepare === "function" && ["launcher","files","clipboard","desktop"].indexOf(route) >= 0) {
            desktop.prepare(route, fresh);
            pendingPrepare = "";
        }
    }
    function finishSync() { root.syncPages(); if (root.active) root.focusDefault(); }
    function scheduleSync() {
        // section, resolvedRoute and family form a dependent binding chain.
        // Wait for that chain to settle; the stable callback also coalesces updates.
        Qt.callLater(root.finishSync);
    }
    onSectionChanged: scheduleSync()
    onResolvedRouteChanged: scheduleSync()
    onFamilyChanged: scheduleSync()
    onActiveChanged: scheduleSync()
    Keys.priority: Keys.BeforeItem
    Keys.onPressed: event => {
        if (event.key === Qt.Key_K && (event.modifiers & Qt.ControlModifier)) {
            root.sectionRequested("launcher"); root.prepare("launcher", false); event.accepted = true;
        } else if (event.key === Qt.Key_Escape) {
            root.dismissRequested();
            event.accepted = true;
        }
    }
    component DeskButton: ActionButton {
        implicitHeight: 40
        textColor: selected ? IslandStyle.accentText : IslandStyle.text
        background: Rectangle { radius: 17; color: parent.selected ? IslandStyle.accent : parent.down || parent.hovered ? IslandStyle.hover : "transparent"; border.width: parent.visualFocus ? 2 : 0; border.color: IslandStyle.accent }
    }
    ColumnLayout {
        id: workspace
        anchors.fill: parent
        spacing: Metrics.space3
        RowLayout {
            id: utilityHeader
            visible: !root.headerEmbedded
            objectName: "islandUtilityHeader"
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            spacing: Metrics.space2
            DeskButton {
                id: searchButton
                objectName: "islandCommandSearch"
                visible: root.resolvedRoute === "controls"
                text: "Search"
                iconName: "terminal"
                iconSize: 16
                tooltip: "Search apps, files and actions · Ctrl+K"
                onClicked: { root.sectionRequested("launcher"); root.prepare("launcher", false); }
            }
            DeskButton {
                objectName: "islandDeskBack"
                visible: root.resolvedRoute !== "controls"
                text: "‹ Back"
                tooltip: "Back to previous page"
                onClicked: { if (!root.back()) root.sectionRequested("controls"); }
            }
            Label {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                visible: root.resolvedRoute !== "controls"
                text: ({launcher:"Search",files:"Files",clipboard:"Clipboard",appearance:"Appearance",widgets:"Widgets",codex:"Codex",help:"Keyboard shortcuts",calendar:"Calendar",wifi:"Wi-Fi",bluetooth:"Bluetooth",audio:"Sound",capture:"Capture",system:"System",power:"Session",settings:"Settings",pomodoro:"Focus",notification:"Notification",inbox:"Notifications",media:"Now playing",thursday:"Thursday"})[root.resolvedRoute] || root.resolvedRoute
                font.pixelSize: 14
                color: IslandStyle.text
                font.weight: Font.DemiBold
            }
            Item { Layout.fillWidth: true; visible: root.resolvedRoute === "controls" }
            DeskButton { objectName: "islandDeskSettings"; visible: root.resolvedRoute === "controls"; iconName: "settings"; iconSize: 17; text: "Settings"; tooltip: "Island settings"; onClicked: root.sectionRequested("settings") }
            DeskButton { objectName: "islandDeskClose"; Layout.preferredWidth: 36; text: "×"; tooltip: "Close island · Escape"; onClicked: root.dismissRequested() }
        }
        Item {
            id: pageArea
            objectName: "islandDeskPageArea"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            Repeater {
                id: pages
                model: ["core", "controls", "thursday", "desktop"]
                Loader {
                    id: loader
                    required property string modelData
                    property bool initialized: modelData === "desktop" || root.family === modelData
                    anchors.fill: parent
                    active: initialized
                    visible: root.family === modelData
                    enabled: visible && root.active
                    opacity: visible ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: IslandStyle.transition; easing.type: Easing.OutCubic } }
                    onVisibleChanged: if (visible) initialized = true
                    Component.onCompleted: {
                        const file = ({core:"IslandCorePage.qml",controls:"IslandControlsPage.qml",thursday:"IslandThursdayPage.qml",desktop:"IslandDesktopPage.qml"})[modelData];
                        setSource(Qt.resolvedUrl(file), modelData === "thursday" ? {backend: Qt.binding(() => root.app.thursdayBackend || null), embedded: true} : {app: root.app});
                    }
                    onLoaded: {
                        if (typeof item.now !== "undefined") item.now = Qt.binding(() => root.now);
                        if (typeof item.mediaPosition !== "undefined") item.mediaPosition = Qt.binding(() => root.mediaPosition);
                        if (typeof item.spectrumSamples !== "undefined") item.spectrumSamples = Qt.binding(() => root.spectrumSamples);
                        root.scheduleSync();
                        if (modelData === "desktop" && root.pendingPrepare) root.prepare(root.pendingPrepare, root.pendingFresh);
                    }
                    Connections {
                        target: loader.item
                        ignoreUnknownSignals: true
                        function onRouteRequested(route) { root.sectionRequested(route); }
                        function onCaptureRequested(annotate) { root.captureRequested(annotate); }
                        function onRecordingRequested() { root.recordingRequested(); }
                        function onFullChatRequested() { root.thursdayFullChatRequested(); }
                        function onDismissRequested() { root.dismissRequested(); }
                    }
                }
            }
        }
    }
}
