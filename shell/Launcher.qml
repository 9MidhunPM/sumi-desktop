pragma ComponentBehavior: Bound

import QtQuick
import QtQml.Models
import QtQuick.Layouts
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "config"
import "services" as S
import "services/LauncherRanking.js" as Ranking
import "components" as C

C.Surface {
    id: root
    required property var app
    property bool embedded: false
    island: embedded
    readonly property color foreground: embedded ? IslandStyle.text : Theme.textMain
    readonly property color secondary: embedded ? IslandStyle.secondary : Theme.textSoft
    readonly property color accent: embedded ? IslandStyle.accent : Theme.accentBlue
    readonly property color accentForeground: embedded ? IslandStyle.accentText : Theme.desktopBackground
    readonly property color separator: embedded ? IslandStyle.line : Theme.borderSoft
    // Six visible matches are enough for discovery; no matches shrink to a hint.
    readonly property real contentHeight: Math.max(0, content.implicitHeight - results.implicitHeight)
        + Math.max(66, Math.min(6, entries.length) * 65 - 5) + (embedded ? 0 : 40)
    readonly property bool shortLayout: !embedded && height < 400
    property bool pageActive: visible
    inset: embedded
    color: embedded ? "transparent" : Theme.glassFill
    border.width: embedded ? 0 : Theme.borderWidth
    enabled: !embedded || pageActive
    property string initialTab: "Apps"
    property string tab: initialTab
    readonly property var tabs: ["Apps", "Files", "Windows", "Actions", "Clipboard"]
    property var fetched: []
    property string error: ""
    property string notice: ""
    property bool activationBusy: false
    property bool resetConfirm: false
    property string savedSelection: ""
    property string savedQuery: ""
    property string savedTab: ""
    property double rankingTime: Date.now() / 1000
    property bool clipboardPaused: false
    property bool clipboardBusy: false
    property bool clipboardHealthy: true
    property int clipboardStatusRevision: 0
    property int clipboardListRevision: 0
    property bool retainClipboardError: false
    property int activeStatusRevision: 0
    property string activeRequestKey: ""
    property bool fetchPending: false
    readonly property string requestKey: tab === "Files" ? "Files:" + search.text : tab === "Clipboard" ? "Clipboard:" + clipboardListRevision : ""
    property var actions: [
        {historyId:"action:appearance",name:"Appearance",detail:"Wallpapers, colors and desktop profiles",panel:"appearance",icon:"󰏘"},
        {historyId:"action:widgets",name:"Desktop widgets",detail:"Priorities, deadline and visible widgets",panel:"widgets",icon:"󰄬"},
        {historyId:"action:settings",name:"Quick settings",detail:"Network, sound and power",panel:"settings",icon:"󰒓"},
        {historyId:"action:notifications",name:"Notifications",detail:"History and Do Not Disturb",panel:"notifications",icon:"󰂚"},
        {historyId:"action:calendar",name:"Calendar",detail:"Today and the monthly calendar",panel:"calendar",icon:"󰃭"},
        {historyId:"action:island",name:"Dynamic island",detail:"Notifications, media and desktop controls",command:"ipc",args:["island","toggle"],icon:"󰎆"},
        {historyId:"action:media",name:"Now playing",detail:"Playback and media controls",panel:"media",icon:"󰎆"},
        {historyId:"action:pomodoro",name:"Pomodoro",detail:"A focused moment",panel:"pomodoro",icon:"󰔟"},
        {historyId:"action:capture-region",name:"Screenshot",detail:"Select a region",command:"capture",args:["region"],icon:"󰄀"},
        {historyId:"action:capture-annotate",name:"Capture and annotate",detail:"Select a region and open Satty",command:"capture",args:["region","annotate"],icon:"󰏫"},
        {historyId:"action:lock",name:"Lock",detail:"Secure this session",command:"lock",args:[],icon:"󰌾"},
        {historyId:"action:help",name:"Keyboard shortcuts",detail:"Your desktop at your fingertips",panel:"help",icon:"󰌌"},
        {historyId:"action:power",name:"Power",detail:"Suspend, logout, restart and shutdown",panel:"power",icon:"󰐥"}
    ]
    // Rebuild catalog only when the desktop entry model changes, not per keystroke.
    readonly property var appCatalog: {
        const applications = DesktopEntries.applications.values.filter(e => !e.noDisplay && !e.id.startsWith("theme-switcher-"));
        const names = Object.create(null);
        applications.forEach(entry => names[entry.name] = (names[entry.name] || 0) + 1);
        return applications.map(function(e) {
            const item = {historyId: "app:" + e.id.replace(/\.desktop$/, ""), name:e.name, detail:e.genericName || e.comment || e.id, entry:e, icon:e.icon};
            item.coldPriority = root.appPriority(item);
            if (names[e.name] > 1) item.detail = e.id.startsWith("brave-") ? "Brave web app" : e.id.startsWith("FFPWA-") ? "Firefox web app" : item.detail + " · " + e.id;
            item.searchName = Ranking.normalize(item.name);
            item.searchDetail = Ranking.normalize(item.detail);
            return item;
        });
    }
    readonly property var actionCatalog: actions.map((entry, index) => Object.assign({}, entry, {coldPriority: index, searchName: Ranking.normalize(entry.name), searchDetail: Ranking.normalize(entry.detail)}))
    readonly property var entries: {
        const query = search.text.toLowerCase().trim();
        let list = [];
        if (tab === "Apps") list = appCatalog;
        else if (tab === "Windows") list = Hyprland.toplevels.values.map(e => ({name:e.title || (e.lastIpcObject ? e.lastIpcObject.title : "Window"),detail:e.lastIpcObject ? e.lastIpcObject.class : "Open window",window:e,icon:""}));
        else if (tab === "Actions") list = actionCatalog;
        else list = fetched;
        if (tab === "Apps" || tab === "Actions") return Ranking.rank(list, query, S.LauncherHistory.document, root.rankingTime);
        return list.filter(e => !query || (e.name + " " + e.detail).toLowerCase().indexOf(query) >= 0);
    }
    width: Math.max(1, Math.min(720, app.activeScreen ? app.activeScreen.width - 48 : 720))
    height: Math.max(1, Math.min(600, app.activeScreen ? app.activeScreen.height - 48 : 600))
    function focusDefault() { search.forceActiveFocus(Qt.ShortcutFocusReason); }
    function selectTab(name) {
        tab = name;
        focusDefault();
    }
    function cycleTab(step) {
        const index = tabs.indexOf(tab);
        selectTab(tabs[(index + step + tabs.length) % tabs.length]);
    }
    function activatePanel(name) {
        rankingTime = Date.now() / 1000;
        resetConfirm = false;
        notice = "";
        retainClipboardError = false;
        const next = name === "files" ? "Files" : name === "clipboard" ? "Clipboard" : "Apps";
        search.text = "";
        if (tab === next) { refresh(); if (tab === "Clipboard") refreshClipboardStatus(); }
        else tab = next;
        results.currentIndex = 0;
        focusDefault();
    }
    function moveSelection(step) {
        if (!entries.length) return;
        results.currentIndex = Math.max(0, Math.min(entries.length - 1, results.currentIndex + step));
        results.positionViewAtIndex(results.currentIndex, ListView.Contain);
    }
    Shortcut { sequence: "Ctrl+Tab"; enabled: !root.embedded && root.visible && root.pageActive; context: Qt.WindowShortcut; onActivated: root.cycleTab(1) }
    Shortcut { sequence: "Ctrl+Shift+Tab"; enabled: !root.embedded && root.visible && root.pageActive; context: Qt.WindowShortcut; onActivated: root.cycleTab(-1) }
    Instantiator {
        model: root.tabs
        delegate: Shortcut { required property string modelData; required property int index; sequence: "Alt+" + (index + 1); enabled: root.visible && root.pageActive; context: Qt.WindowShortcut; onActivated: root.selectTab(modelData) }
    }
    function appPriority(entry) {
        const name = ((entry.name || "") + " " + (entry.entry ? entry.entry.id : "")).toLowerCase();
        const favorites = ["kitty", "thunar", "brave", "antigravity", "papers", "loupe", "ghostty"];
        const rank = favorites.findIndex(favorite => name.indexOf(favorite) >= 0);
        return rank < 0 ? favorites.length : rank;
    }
    Connections {
        target: S.LauncherHistory
        function onChanging() {
            const preserve = S.LauncherHistory.loaded || results.currentIndex > 0 || search.text.length > 0;
            root.savedSelection = preserve ? (root.entries[results.currentIndex] || {}).historyId || "" : "";
            root.savedQuery = search.text;
            root.savedTab = root.tab;
        }
        function onDocumentChanged() {
            Qt.callLater(() => {
                if (root.savedQuery !== search.text || root.savedTab !== root.tab) return;
                const index = root.entries.findIndex(entry => entry.historyId === root.savedSelection);
                results.currentIndex = Math.max(0, index);
                results.positionViewAtIndex(results.currentIndex, ListView.Contain);
            });
        }
    }
    function currentRequestKey() {
        return root.tab === "Files" ? "Files:" + search.text : root.tab === "Clipboard" ? "Clipboard:" + root.clipboardListRevision : "";
    }
    function refresh(preserveError) {
        debounce.stop();
        root.fetched = [];
        if (!preserveError && !(root.tab === "Clipboard" && root.retainClipboardError)) root.error = "";
        const latestKey = root.currentRequestKey();
        if (!latestKey) { root.fetchPending = false; return; }
        if (fetcher.running) { root.fetchPending = true; return; }
        root.fetchPending = false;
        root.activeRequestKey = latestKey;
        fetcher.command = [S.Desktop.controller, "action", root.tab === "Files" ? "search-files" : "clipboard", root.tab === "Files" ? search.text : "list"];
        fetcher.running = true;
    }
    function refreshClipboardStatus() {
        if (!clipboardStatus.running) {
            root.activeStatusRevision = root.clipboardStatusRevision;
            clipboardStatus.running = true;
        }
    }
    function clipboardCommand(args, callback) {
        if (root.clipboardBusy) return;
        root.clipboardBusy = true;
        root.clipboardStatusRevision += 1;
        root.clipboardListRevision += 1;
        S.Desktop.action("clipboard", args, function(ok, value, error) {
            root.clipboardBusy = false;
            if (!ok) {
                root.retainClipboardError = true;
                root.error = error;
                if (root.tab === "Clipboard" && (root.fetchPending || fetcher.running)) root.refresh(true);
                return;
            }
            root.error = "";
            root.retainClipboardError = false;
            if (typeof value.paused === "boolean") root.clipboardPaused = value.paused;
            if (typeof value.healthy === "boolean") root.clipboardHealthy = value.healthy;
            if (typeof callback === "function") callback();
            if (root.tab === "Clipboard" && (root.fetchPending || fetcher.running)) root.refresh();
        });
    }
    function toggleClipboard() {
        clipboardCommand([root.clipboardPaused ? "resume" : "pause"], null);
    }
    function deleteClipboard(id) {
        clipboardCommand(["delete", id], function() { root.fetched = root.fetched.filter(entry => entry.id !== id); });
    }
    function clearClipboard() {
        clipboardCommand(["clear"], function() { root.fetched = []; });
    }
    function activate(entry) {
        if (!entry || activationBusy) return;
        const historyId = (tab === "Apps" || tab === "Actions") ? entry.historyId : "";
        const query = Ranking.normalize(search.text);
        if (entry.panel) {
            if (app.open(entry.panel, null) === true) S.LauncherHistory.record(historyId, query);
            return;
        }
        let command = "";
        let args = [];
        if (entry.entry) {
            command = "launch-desktop";
            args = [entry.entry.id];
        } else if (entry.window) {
            app.close();
            Qt.callLater(() => S.HyprlandActions.focusWindow(entry.window.address));
            return;
        }
        else if (tab === "Files") { command = "open"; args = [entry.path]; }
        else if (tab === "Clipboard") { command = "clipboard"; args = ["copy", entry.id]; }
        else if (entry.command) { command = entry.command; args = entry.args || []; }
        if (!command) return;
        // Interactive desktop actions need the overlay released before they
        // begin. Ordinary launches stay visible until the controller accepts
        // them, so a failed application does not silently disappear.
        if (command === "capture" && root.embedded && typeof app.selectCapture === "function") { app.selectCapture(args.indexOf("annotate") >= 0, false); return; }
        if (command === "capture" || command === "lock" || (command === "ipc" && args[0] === "island")) {
            app.close();
            S.Desktop.action(command, args, function(ok, value, error) {
                if (ok && value.cancelled !== true) S.LauncherHistory.record(historyId, query);
            });
            return;
        }
        root.activationBusy = true;
        root.error = "";
        S.Desktop.action(command, args, function(ok, value, error) {
            root.activationBusy = false;
            if (ok) {
                if (value.cancelled !== true) S.LauncherHistory.record(historyId, query);
                if (root.embedded && command === "clipboard") root.notice = "Copied";
                else root.app.close();
            }
            else root.error = error || "Could not open " + entry.name + ".";
        });
    }
    onTabChanged: { notice = ""; resetConfirm = false; retainClipboardError = false; results.currentIndex = 0; refresh(); if (tab === "Clipboard") refreshClipboardStatus(); }
    Component.onCompleted: { if (!embedded) focusDefault(); refresh(); if (tab === "Clipboard") refreshClipboardStatus(); }
    Process {
        id: fetcher
        stdout: StdioCollector {
            onStreamFinished: {
                if (root.activeRequestKey !== root.currentRequestKey()) return;
                try { root.fetched = JSON.parse(text); }
                catch (e) { root.error = "Could not load results"; }
            }
        }
        stderr: StdioCollector { onStreamFinished: if (root.activeRequestKey === root.currentRequestKey() && text.trim()) root.error = text.trim() }
        onExited: {
            const latestKey = root.currentRequestKey();
            if (root.clipboardBusy && root.tab === "Clipboard") { root.fetchPending = true; return; }
            if (latestKey && (root.fetchPending || root.activeRequestKey !== latestKey))
                Qt.callLater(root.refresh);
        }
    }
    Process {
        id: clipboardStatus
        command: [S.Desktop.controller, "action", "clipboard", "status"]
        stdout: StdioCollector {
            onStreamFinished: {
                if (root.activeStatusRevision !== root.clipboardStatusRevision) return;
                try {
                    const status = JSON.parse(text);
                    if (typeof status.paused === "boolean") root.clipboardPaused = status.paused;
                    root.clipboardHealthy = status.healthy !== false;
                } catch (e) { /* Status failure must not hide clipboard entries. */ }
            }
        }
    }
    Timer { id: debounce; interval: 180; onTriggered: root.refresh() }
    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: root.embedded ? 0 : root.shortLayout ? 16 : 20
        spacing: root.shortLayout ? 6 : 12
        RowLayout {
            Layout.fillWidth: true
            C.Label { text: "󰀻"; color: root.accent; font.pixelSize: 22 }
            TextField {
                id: search
                objectName: "launcherSearch"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                implicitHeight: root.shortLayout ? 40 : 46
                placeholderText: root.tab === "Files" ? "Find a file by name…" : root.tab === "Apps" ? "Search applications…" : "Search " + root.tab.toLowerCase() + "…"
                color: root.foreground
                placeholderTextColor: root.secondary
                font.family: Theme.font
                font.pixelSize: root.embedded ? 16 : 20
                selectByMouse: true
                leftPadding: 14
                rightPadding: 14
                background: C.Surface { island: root.embedded; inset: true; radius: IslandStyle.controlRadius; border.width: search.activeFocus ? 1 : 0; border.color: Theme.borderStrong }
                onTextChanged: { root.rankingTime = Date.now() / 1000; root.resetConfirm = false; results.currentIndex = 0; if (root.tab === "Files") debounce.restart(); }
                Keys.onDownPressed: root.moveSelection(1)
                Keys.onUpPressed: root.moveSelection(-1)
                Keys.onReturnPressed: root.activate(root.entries[results.currentIndex])
                Keys.onEnterPressed: root.activate(root.entries[results.currentIndex])
                Keys.onEscapePressed: event => { if (root.embedded) event.accepted = false; else root.app.close(); }
            }
            C.ActionButton { island: root.embedded; visible: !root.embedded; text: "Esc"; quiet: true; onClicked: root.app.close() }
        }
        Flow {
            Layout.fillWidth: true
            spacing: Metrics.space2
            Repeater { model: root.tabs; C.ActionButton { island: root.embedded; required property string modelData; text: modelData; selected: root.tab === modelData; quiet: true; onClicked: root.selectTab(modelData) } }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: root.separator }
        C.Label { visible: root.notice.length > 0 || root.error.length > 0 || (root.tab === "Clipboard" && !root.clipboardHealthy); text: root.error || root.notice || "Clipboard capture is unavailable. Resume to restart both watchers."; color: root.notice.length && !root.error.length ? root.foreground : Theme.accentPink; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
        C.Label { visible: (root.tab === "Apps" || root.tab === "Actions") && S.LauncherHistory.error.length > 0; text: S.LauncherHistory.error; color: Theme.accentWarn; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
        ListView {
            id: results
            implicitHeight: 380
            Layout.fillHeight: true
            Layout.fillWidth: true
            Layout.minimumHeight: 66
            clip: true
            spacing: 5
            model: root.entries
            currentIndex: 0
            reuseItems: true
            boundsBehavior: Flickable.StopAtBounds
            keyNavigationEnabled: false
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                width: results.width
                height: 60
                radius: IslandStyle.controlRadius
                color: root.embedded ? (results.currentIndex === index ? IslandStyle.hover : hover.containsMouse ? IslandStyle.raised : "transparent") : results.currentIndex === index ? Theme.bgPlaying : hover.containsMouse ? Theme.bgPanel : "transparent"
                border.width: !root.embedded && results.currentIndex === index ? 1 : 0
                border.color: root.separator
                Rectangle { visible: !root.embedded && results.currentIndex === row.index; width: 3; height: 24; radius: 2; color: root.accent; anchors.left: parent.left; anchors.leftMargin: 1; anchors.verticalCenter: parent.verticalCenter }
                RowLayout {
                    z: 1
                    anchors.fill: parent
                    anchors.margins: Metrics.space3
                    spacing: 14
                    Item {
                        Layout.preferredWidth: 36
                        Layout.preferredHeight: 36
                        Image {
                            id: appIcon
                            anchors.fill: parent
                            source: root.tab === "Apps" && row.modelData.icon ? Quickshell.iconPath(row.modelData.icon, true) : ""
                            sourceSize: Qt.size(40, 40)
                            fillMode: Image.PreserveAspectFit
                            visible: status === Image.Ready
                        }
                        C.Label {
                            anchors.centerIn: parent
                            visible: !appIcon.visible
                            text: root.tab === "Files" ? (row.modelData.directory ? "󰉋" : "󰈙") : root.tab === "Clipboard" ? "󰅍" : root.tab === "Actions" ? (row.modelData.icon || "󰀻") : "󰀻"
                            color: root.accent
                            font.pixelSize: 22
                        }
                    }
                    ColumnLayout { Layout.fillWidth: true; spacing: 3; C.Label { color: root.foreground; text: row.modelData.name || ""; Layout.fillWidth: true; font.pixelSize: 15; font.weight: Font.Medium } C.Label { text: row.modelData.detail || ""; Layout.fillWidth: true; font.pixelSize: 12; color: root.secondary } }
                    C.ActionButton { island: root.embedded; visible: root.tab === "Clipboard"; text: "Delete"; quiet: true; implicitHeight: 30; onClicked: root.deleteClipboard(row.modelData.id) }
                    C.Label { visible: results.currentIndex === row.index; text: "↵"; color: root.accent }
                }
                MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; onPositionChanged: results.currentIndex = row.index; onClicked: root.activate(row.modelData) }
            }
            C.Label { anchors.centerIn: parent; visible: root.entries.length === 0; text: root.error || (((root.tab === "Files" || root.tab === "Clipboard") && (root.activeRequestKey === root.currentRequestKey() && fetcher.running || root.fetchPending || (root.tab === "Files" && debounce.running))) ? "Searching…" : root.tab === "Files" && search.text.length < 2 ? "Type at least two letters to find files" : "Nothing here yet"); color: root.secondary }
        }
        RowLayout {
            Layout.fillWidth: true
            C.Label { visible: root.width >= 500; text: root.embedded ? "↑ ↓ select    ↵ open    Alt 1–5 category" : "↑ ↓ select    ↵ open    Ctrl Tab switch    Esc close"; color: root.secondary; font.pixelSize: 11; Layout.fillWidth: true; Layout.minimumWidth: 0 }
            C.ActionButton { island: root.embedded; objectName: "launcherResetLearning"; visible: (root.tab === "Apps" || root.tab === "Actions") && !root.resetConfirm; enabled: !root.activationBusy && !S.LauncherHistory.busy; text: "Reset learning"; font.pixelSize: 11; quiet: true; tooltip: "Clear the local app and action choices used to rank results"; onClicked: root.resetConfirm = true }
            C.ActionButton { island: root.embedded; visible: root.tab === "Clipboard"; enabled: !root.clipboardBusy; text: root.clipboardBusy ? "Updating…" : root.clipboardPaused ? "Resume" : "Pause"; quiet: true; tooltip: root.clipboardPaused ? "Resume saving clipboard history" : "Pause saving clipboard history"; onClicked: root.toggleClipboard() }
            C.ActionButton { island: root.embedded; visible: root.tab === "Clipboard"; enabled: !root.clipboardBusy; text: "Clear history"; quiet: true; onClicked: root.clearClipboard() }
        }
        RowLayout {
            visible: root.resetConfirm && (root.tab === "Apps" || root.tab === "Actions")
            Layout.fillWidth: true
            C.Label { text: "Forget learned app and action choices?"; color: root.secondary; font.pixelSize: 12; Layout.fillWidth: true; Layout.minimumWidth: 0; wrapMode: Text.Wrap }
            C.ActionButton { island: root.embedded; text: "Cancel"; quiet: true; onClicked: root.resetConfirm = false }
            C.ActionButton { island: root.embedded; text: "Reset"; enabled: !S.LauncherHistory.busy; onClicked: { root.resetConfirm = false; S.LauncherHistory.reset(); } }
        }
    }
}
