pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"
import ".." as Shell

// Cached tools share the island's geometry and retain unfinished work.
FocusScope {
    id: root
    required property var app
    property string route: "desktop"
    property bool active: false
    property string pendingRoute: "launcher"
    property bool pendingFresh: false
    readonly property bool searching: ["desktop", "launcher", "files", "clipboard"].indexOf(route) >= 0
    readonly property bool ready: launcher.status === Loader.Ready
    readonly property var measuredPage: searching ? launcher.item : route === "appearance" ? appearance.item
        : route === "widgets" ? widgets.item : route === "help" ? help.item : null
    // Layouts may resolve their implicit sizes while the cached loader changes
    // page. Sample after that turn so the host never asks the same layout for
    // its size recursively while applying the previous measurement.
    property real measuredNaturalHeight: 240
    readonly property real contentHeight: measuredNaturalHeight
    readonly property var sizeSource: measuredPage || (route === "codex" ? codex.item : null)
    function measureContent() {
        const page = sizeSource;
        const value = page && typeof page.contentHeight === "number" ? page.contentHeight
            : page && typeof page.preferredHeight === "number" ? page.preferredHeight : 240;
        if (isFinite(value) && value >= 0) measuredNaturalHeight = Math.ceil(value);
    }
    function queueMeasurement() { Qt.callLater(root.measureContent); }
    onSizeSourceChanged: queueMeasurement()
    onWidthChanged: queueMeasurement()
    Connections {
        target: root.sizeSource
        ignoreUnknownSignals: true
        function onContentHeightChanged() { root.queueMeasurement(); }
        function onPreferredHeightChanged() { root.queueMeasurement(); }
    }
    signal routeRequested(string route)
    function focusDefault() {
        const page = searching ? launcher.item : route === "appearance" ? appearance.item : route === "widgets" ? widgets.item : route === "help" ? help.item : null;
        if (page && typeof page.focusDefault === "function") page.focusDefault();
        else root.forceActiveFocus(Qt.OtherFocusReason);
    }
    function prepare(name, fresh) {
        pendingRoute = name; pendingFresh = fresh;
        if (!searching && ["launcher", "files", "clipboard"].indexOf(name) < 0) return;
        if (!launcher.item) return;
        if (fresh) launcher.item.activatePanel(name);
        else {
            const category = name === "files" ? "Files" : name === "clipboard" ? "Clipboard" : "Apps";
            if (launcher.item.tab !== category) launcher.item.tab = category;
        }
        pendingFresh = false;
    }
    function warmRoute() {
        if (searching) prepare(route, false);
        if (route === "appearance") appearance.initialized = true;
        else if (route === "widgets") widgets.initialized = true;
        else if (route === "help") help.initialized = true;
        else if (route === "codex") codex.initialized = true;
    }
    onRouteChanged: { Qt.callLater(warmRoute); queueMeasurement(); }
    Component.onCompleted: { warmRoute(); queueMeasurement(); }
    function back() { return false; }
    onActiveChanged: if (active) Qt.callLater(focusDefault)
    Loader {
        id: launcher
        objectName: "islandDesktopLauncherLoader"
        anchors.fill: parent
        active: true
        visible: root.searching
        enabled: root.active && visible
        onLoaded: if (root.searching) root.prepare(root.pendingFresh ? root.pendingRoute : root.route, root.pendingFresh)
        sourceComponent: Shell.Launcher { app: root.app; embedded: true; pageActive: root.active && root.searching }
    }
    Loader {
        id: appearance
        objectName: "islandDesktopAppearanceLoader"
        property bool initialized: false
        anchors.fill: parent
        active: initialized
        visible: root.route === "appearance"
        enabled: root.active && visible
        sourceComponent: Shell.Appearance { app: root.app; embedded: true; pageActive: root.active && root.route === "appearance" }
    }
    Loader {
        id: widgets
        objectName: "islandDesktopWidgetsLoader"
        property bool initialized: false
        anchors.fill: parent
        active: initialized
        visible: root.route === "widgets"
        enabled: root.active && visible
        sourceComponent: Shell.WidgetsEditor { app: root.app; embedded: true; pageActive: root.active && root.route === "widgets" }
    }
    Loader {
        id: help
        objectName: "islandDesktopHelpLoader"
        property bool initialized: false
        anchors.fill: parent
        active: initialized
        visible: root.route === "help"
        enabled: root.active && visible
        onLoaded: item.activatePanel()
        sourceComponent: Shell.Dashboard { app: root.app; kind: "help"; embedded: true; pageActive: root.active && root.route === "help" }
    }
    Loader {
        id: codex
        objectName: "islandDesktopCodexLoader"
        property bool initialized: false
        readonly property var controller: typeof root.app.codexStatus !== "undefined" ? root.app.codexStatus : null
        readonly property string dashboardSource: typeof root.app.codexDashboardSource !== "undefined" ? String(root.app.codexDashboardSource) : ""
        readonly property bool ownsView: root.active && visible && !!item
        anchors.fill: parent
        active: !!controller && dashboardSource.length > 0 && initialized
        visible: root.route === "codex"
        enabled: root.active && visible
        function loadDashboard() {
            if (!active) return;
            setSource(dashboardSource, {
                controller: Qt.binding(() => codex.controller),
                hostWindowVisible: Qt.binding(() => root.active && root.route === "codex")
            });
        }
        function syncView() {
            if (!controller) return;
            if (ownsView) controller.dashboardView = item;
            else if (controller.dashboardView === item) controller.dashboardView = null;
        }
        onActiveChanged: if (active) loadDashboard()
        onDashboardSourceChanged: if (active) loadDashboard()
        onOwnsViewChanged: syncView()
        onLoaded: syncView()
        Component.onDestruction: if (controller && controller.dashboardView === item) controller.dashboardView = null
        Connections {
            target: codex.item
            function onCloseRequested() {
                if (!root.app.islandSession || !root.app.islandSession.back()) root.routeRequested("controls");
            }
        }
    }
    Label { anchors.centerIn: parent; width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; visible: root.route === "codex" && (!codex.controller || !codex.dashboardSource || codex.status === Loader.Error); text: "Codex status is unavailable. Start the local status service to connect."; color: IslandStyle.secondary; font.pixelSize: 14 }
}
