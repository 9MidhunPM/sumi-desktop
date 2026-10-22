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
    property string initialTab: "Apps"
    property string tab: initialTab
    readonly property var tabs: ["Apps", "Files", "Windows", "Actions", "Clipboard"]
    property var fetched: []
    property string error: ""
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
        {historyId:"action:appearance",name:"Appearance",detail:"Wallpapers, colors and desktop preferences",panel:"appearance",icon:"󰏘"},
        {historyId:"action:widgets",name:"Desktop widgets",detail:"Priorities, deadline and visible widgets",panel:"widgets",icon:"󰄬"},
        {historyId:"action:settings",name:"Quick settings",detail:"Network, sound and power",panel:"settings",icon:"󰒓"},
        {historyId:"action:notifications",name:"Notifications",detail:"History and Do Not Disturb",panel:"notifications",icon:"󰂚"},
        {historyId:"action:calendar",name:"Calendar",detail:"Today and the monthly calendar",panel:"calendar",icon:"󰃭"},
        {historyId:"action:media",name:"Now playing",detail:"Playback and media controls",panel:"media",icon:"󰎆"},
        {historyId:"action:pomodoro",name:"Pomodoro",detail:"A focused moment",panel:"pomodoro",icon:"󰔟"},
        {historyId:"action:capture-region",name:"Screenshot",detail:"Select a region",command:"capture",args:["region"],icon:"󰄀"},
        {historyId:"action:capture-annotate",name:"Capture and annotate",detail:"Select a region and open Satty",command:"capture",args:["region","annotate"],icon:"󰏫"},
        {historyId:"action:lock",name:"Lock",detail:"Secure this session",command:"lock",args:[],icon:"󰌾"},
        {historyId:"action:help",name:"Keyboard shortcuts",detail:"Your desktop at your fingertips",panel:"help",icon:"󰌌"},
        {historyId:"action:power",name:"Power",detail:"Suspend, logout, restart and shutdown",panel:"power",icon:"󰐥"}
    ]
    readonly property var entries: {
        const query = search.text.toLowerCase().trim();
        let list = [];
        if (tab === "Apps") {
            const applications = DesktopEntries.applications.values.filter(e => !e.noDisplay && !e.id.startsWith("theme-switcher-"));
            const names = Object.create(null);
            applications.forEach(entry => names[entry.name] = (names[entry.name] || 0) + 1);
            list = applications.map(function(e) {
                const item = {historyId: "app:" + e.id.replace(/\.desktop$/, ""), name:e.name, detail:e.genericName || e.comment || e.id, entry:e, icon:e.icon};
                item.coldPriority = root.appPriority(item);
                const duplicate = names[e.name] > 1;
                if (duplicate) item.detail = e.id.startsWith("brave-") ? "Brave web app" : e.id.startsWith("FFPWA-") ? "Firefox web app" : item.detail + " · " + e.id;
                return item;
            });
        } else if (tab === "Windows") {
            list = Hyprland.toplevels.values.map(e => ({name:e.title || (e.lastIpcObject ? e.lastIpcObject.title : "Window"),detail:e.lastIpcObject ? e.lastIpcObject.class : "Open window",window:e,icon:""}));
        } else if (tab === "Actions") list = actions.map((entry, index) => Object.assign({}, entry, {coldPriority: index}));
        else list = fetched;
        if (tab === "Apps" || tab === "Actions") return Ranking.rank(list, query, S.LauncherHistory.document, root.rankingTime);
        return list.filter(e => !query || (e.name + " " + e.detail).toLowerCase().indexOf(query) >= 0);
    }
    width: Math.min(680, app.activeScreen ? app.activeScreen.width - 80 : 680)
    height: Math.min(570, app.activeScreen ? app.activeScreen.height - 80 : 570,
                     Math.max(220, content.implicitHeight + 40))
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
    Shortcut { sequence: "Ctrl+Tab"; enabled: root.visible; context: Qt.WindowShortcut; onActivated: root.cycleTab(1) }
    Shortcut { sequence: "Ctrl+Shift+Tab"; enabled: root.visible; context: Qt.WindowShortcut; onActivated: root.cycleTab(-1) }
    Instantiator {
        model: root.tabs
        delegate: Shortcut { required property string modelData; required property int index; sequence: "Alt+" + (index + 1); enabled: root.visible; context: Qt.WindowShortcut; onActivated: root.selectTab(modelData) }
    }
    function appPriority(entry) {
        const name = ((entry.name || "") + " " + (entry.entry ? entry.entry.id : "")).toLowerCase();
        const favorites = ["kitty", "thunar", "firefox", "papers", "loupe"];
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
        if (command === "capture" || command === "lock") {
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
                root.app.close();
            }
            else root.error = error || "Could not open " + entry.name + ".";
        });
    }
    onTabChanged: { resetConfirm = false; retainClipboardError = false; results.currentIndex = 0; refresh(); if (tab === "Clipboard") refreshClipboardStatus(); }
    Component.onCompleted: { focusDefault(); refresh(); if (tab === "Clipboard") refreshClipboardStatus(); }
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
        anchors.margins: 20
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            C.Label { text: "󰀻"; color: Theme.accentBlue; font.pixelSize: 22 }
            TextField {
                id: search
                Layout.fillWidth: true
                placeholderText: root.tab === "Files" ? "Find a file by name…" : "Search apps, files, commands…"
                color: Theme.textMain
                placeholderTextColor: Theme.textSoft
                font.family: Theme.font
                font.pixelSize: 18
                selectByMouse: true
                background: Item {}
                onTextChanged: { root.rankingTime = Date.now() / 1000; root.resetConfirm = false; results.currentIndex = 0; if (root.tab === "Files") debounce.restart(); }
                Keys.onDownPressed: root.moveSelection(1)
                Keys.onUpPressed: root.moveSelection(-1)
                Keys.onReturnPressed: root.activate(root.entries[results.currentIndex])
                Keys.onEnterPressed: root.activate(root.entries[results.currentIndex])
                Keys.onEscapePressed: root.app.close()
            }
            C.ActionButton { text: "Esc"; quiet: true; onClicked: root.app.close() }
        }
        RowLayout {
            spacing: 6
            Repeater { model: root.tabs; C.ActionButton { required property string modelData; text: modelData; selected: root.tab === modelData; quiet: true; onClicked: root.selectTab(modelData) } }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.borderSoft }
        C.Label { visible: root.error.length > 0 || (root.tab === "Clipboard" && !root.clipboardHealthy); text: root.error || "Clipboard capture is unavailable. Resume to restart both watchers."; color: Theme.accentPink; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
        C.Label { visible: (root.tab === "Apps" || root.tab === "Actions") && S.LauncherHistory.error.length > 0; text: S.LauncherHistory.error; color: Theme.accentWarn; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
        ListView {
            id: results
            implicitHeight: Math.max(66, root.entries.length * 71 - 5)
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
                height: 66
                radius: 10
                color: results.currentIndex === index ? Theme.bgPlaying : hover.containsMouse ? Theme.bgPanel : "transparent"
                RowLayout {
                    z: 1
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 14
                    Item {
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
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
                            color: Theme.accentBlue
                            font.pixelSize: 22
                        }
                    }
                    ColumnLayout { Layout.fillWidth: true; spacing: 3; C.Label { text: row.modelData.name || ""; Layout.fillWidth: true; font.weight: Font.Medium } C.Label { text: row.modelData.detail || ""; Layout.fillWidth: true; font.pixelSize: 12; color: Theme.textSoft } }
                    C.ActionButton { visible: root.tab === "Clipboard"; text: "Delete"; quiet: true; implicitHeight: 30; onClicked: root.deleteClipboard(row.modelData.id) }
                    C.Label { visible: results.currentIndex === row.index; text: "↵"; color: Theme.accentBlue }
                }
                MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; onPositionChanged: results.currentIndex = row.index; onClicked: root.activate(row.modelData) }
            }
            C.Label { anchors.centerIn: parent; visible: root.entries.length === 0; text: root.error || (root.tab === "Files" && search.text.length < 2 ? "Type at least two letters to find files" : "Nothing here yet"); color: Theme.textSoft }
        }
        RowLayout {
            Layout.fillWidth: true
            C.Label { text: "↑ ↓ select    ↵ open    Ctrl Tab switch    Esc close"; color: Theme.textSoft; font.pixelSize: 11; Layout.fillWidth: true }
            C.ActionButton { objectName: "launcherResetLearning"; visible: (root.tab === "Apps" || root.tab === "Actions") && !root.resetConfirm; enabled: !root.activationBusy && !S.LauncherHistory.busy; text: "Reset learning"; font.pixelSize: 11; quiet: true; tooltip: "Clear the local app and action choices used to rank results"; onClicked: root.resetConfirm = true }
            C.ActionButton { visible: root.tab === "Clipboard"; enabled: !root.clipboardBusy; text: root.clipboardBusy ? "Updating…" : root.clipboardPaused ? "Resume" : "Pause"; quiet: true; tooltip: root.clipboardPaused ? "Resume saving clipboard history" : "Pause saving clipboard history"; onClicked: root.toggleClipboard() }
            C.ActionButton { visible: root.tab === "Clipboard"; enabled: !root.clipboardBusy; text: "Clear history"; quiet: true; onClicked: root.clearClipboard() }
        }
        RowLayout {
            visible: root.resetConfirm && (root.tab === "Apps" || root.tab === "Actions")
            Layout.fillWidth: true
            C.Label { text: "Forget learned app and action choices?"; color: Theme.textSoft; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
            C.ActionButton { text: "Cancel"; quiet: true; onClicked: root.resetConfirm = false }
            C.ActionButton { text: "Reset"; enabled: !S.LauncherHistory.busy; onClicked: { root.resetConfirm = false; S.LauncherHistory.reset(); } }
        }
    }
}
