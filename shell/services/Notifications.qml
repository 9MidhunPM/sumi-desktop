pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Notifications as N
import "../config" as C

Singleton {
    id: root
    readonly property bool enabled: !Desktop.preview
    readonly property bool dnd: C.Settings.dnd
    property var history: []
    readonly property var active: history.filter(entry => entry.popup)
    readonly property int count: history.length
    readonly property int unread: history.filter(entry => entry.unread).length
    property var live: ({})
    property var expiryTimers: ({})
    property var pendingUpdates: ({})
    property var watchedActions: ({})
    property bool historyLoaded: Desktop.preview
    property bool savePending: false
    property string storageError: ""
    readonly property bool persistenceBusy: historyLoader.running || historySaver.running || savePending
    signal received(var entry)

    onHistoryChanged: if (root.historyLoaded && !Desktop.preview) root.saveHistory()

    function saveHistory(): void {
        if (historySaver.running) { root.savePending = true; return; }
        root.savePending = false;
        historySaver.payload = JSON.stringify(root.history);
        historySaver.stdinEnabled = true;
        historySaver.running = true;
    }

    function restoreHistory(entries: var): void {
        const current = root.history;
        const archived = entries.slice(0, 100).map(function(entry, index) {
            const parsedTime = new Date(entry.time);
            // Archived IDs cannot collide with a new server's IDs.
            return Object.assign({}, entry, {id: -index - 1, time: isNaN(parsedTime.getTime()) ? new Date() : parsedTime,
                actions: [], popup: false, transient: false});
        });
        const merged = current.map(function(entry) {
            const index = archived.findIndex(old => entry.restored && old.originalId === entry.id
                && old.appName === entry.appName && old.summary === entry.summary);
            if (index < 0) return entry;
            const previous = archived.splice(index, 1)[0];
            return Object.assign({}, entry, {time: previous.time, unread: previous.unread});
        });
        root.history = merged.concat(archived).sort((left, right) => right.time.getTime() - left.time.getTime()).slice(0, 100);
    }

    Process {
        id: historyLoader
        command: [Desktop.controller, "notifications", "load"]
        running: !Desktop.preview
        stdout: StdioCollector { id: historyData }
        stderr: StdioCollector {}
        onExited: (code, status) => {
            if (code === 0) {
                try {
                    root.restoreHistory(JSON.parse(historyData.text).entries);
                } catch (error) { root.storageError = "Notification history could not be read."; }
            } else root.storageError = "Notification history could not be read.";
            root.historyLoaded = true;
            // Notifications arriving while disk history loads must also persist.
            if (Object.keys(root.live).length) root.saveHistory();
        }
    }
    Process {
        id: historySaver
        property string payload: ""
        command: [Desktop.controller, "notifications", "save"]
        stdout: StdioCollector {}
        stderr: StdioCollector {}
        onStarted: { write(payload); stdinEnabled = false; }
        onExited: (code, status) => {
            root.storageError = code === 0 ? "" : "Notification history could not be saved.";
            if (root.savePending) Qt.callLater(root.saveHistory);
        }
    }

    onDndChanged: {
        if (dnd) root.history = root.history.map(entry => Object.assign({}, entry, {popup: false}));
    }

    function plain(value: string): string {
        return value.replace(/<[^>]*>/g, "")
            .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
            .replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, "&")
            .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "");
    }

    function accept(notification: var): void {
        notification.tracked = true;
        const id = notification.id;
        const alreadyConnected = root.live[id] === notification;
        root.live[id] = notification;
        if (!alreadyConnected) {
            notification.closed.connect(function() { root.closed(id); });
            // Replace-ID requests update the native QObject in place. The
            // server's notification signal is emitted only for new IDs.
            for (const signalName of ["appNameChanged", "summaryChanged", "bodyChanged", "appIconChanged", "urgencyChanged", "actionsChanged", "expireTimeoutChanged", "transientChanged"]) {
                const changed = notification[signalName];
                if (changed && typeof changed.connect === "function")
                    changed.connect(function() { root.scheduleUpdate(id); });
            }
        }
        root.updateSnapshot(notification, !alreadyConnected, false);
    }

    function scheduleUpdate(id: int): void {
        if (root.pendingUpdates[id]) return;
        root.pendingUpdates[id] = true;
        Qt.callLater(function() {
            delete root.pendingUpdates[id];
            const notification = root.live[id];
            if (notification) root.updateSnapshot(notification, false, true);
        });
    }

    function updateSnapshot(notification: var, first: bool, updated: bool): void {
        const id = notification.id;
        const observedActions = root.watchedActions[id] || [];
        for (const action of notification.actions) {
            if (observedActions.indexOf(action) < 0 && action.textChanged && typeof action.textChanged.connect === "function")
                action.textChanged.connect(function() { root.scheduleUpdate(id); });
        }
        root.watchedActions[id] = notification.actions.slice();
        const restored = first && notification.lastGeneration === true;
        const previous = root.history.find(entry => entry.id === id)
            || (restored ? root.history.find(entry => entry.id < 0 && entry.originalId === id
                && entry.appName === plain(notification.appName || "Notification")
                && entry.summary === plain(notification.summary || "")) : null);
        const entry = {
            id: id,
            appName: plain(notification.appName || "Notification"),
            summary: plain(notification.summary || ""),
            body: plain(notification.body || ""),
            appIcon: notification.appIcon || "",
            time: previous ? previous.time : new Date(),
            critical: notification.urgency === N.NotificationUrgency.Critical,
            actions: notification.actions.map(action => plain(action.text)),
            transient: notification.transient === true,
            restored: restored,
            unread: previous ? previous.unread : !restored,
            popup: previous && !updated ? previous.popup : !root.dnd && !restored
        };
        const nextHistory = previous ? root.history.map(item => item.id === previous.id ? entry : item) : [entry].concat(root.history);
        for (const oldEntry of nextHistory.slice(100)) {
            if (root.live[oldEntry.id]) root.live[oldEntry.id].dismiss();
        }
        root.history = nextHistory.slice(0, 100);
        if (root.expiryTimers[id]) {
            root.expiryTimers[id].destroy();
            delete root.expiryTimers[id];
        }
        let timeout = notification.expireTimeout;
        if (timeout < 0) timeout = entry.critical ? 0 : 6000;
        if (timeout > 0) root.expiryTimers[id] = expiryFactory.createObject(root, {notificationId: id, interval: timeout, running: true});
        if (first && !restored) root.received(entry);
    }

    function closed(id: int): void {
        delete root.live[id];
        delete root.pendingUpdates[id];
        delete root.watchedActions[id];
        if (root.expiryTimers[id]) {
            root.expiryTimers[id].destroy();
            delete root.expiryTimers[id];
        }
        root.history = root.history.filter(entry => entry.id !== id || !entry.transient).map(function(entry) {
            if (entry.id === id) return Object.assign({}, entry, {popup: false, actions: []});
            return entry;
        });
    }

    function expire(id: int): void {
        const notification = root.live[id];
        if (notification) notification.expire();
        else root.closed(id);
    }

    function dismiss(id: int): void {
        const notification = root.live[id];
        if (notification) notification.dismiss();
        root.history = root.history.filter(entry => entry.id !== id);
    }

    function clear(): void {
        for (const id of Object.keys(root.live)) root.live[id].dismiss();
        root.history = [];
    }

    function invoke(id: int, actionIndex: int): void {
        const notification = root.live[id];
        if (notification && notification.actions[actionIndex]) notification.actions[actionIndex].invoke();
    }

    function markRead(): void { root.history = root.history.map(entry => Object.assign({}, entry, {unread: false})); }
    function toggleDnd(): void { C.Settings.toggle("dnd"); }

    Component {
        id: expiryFactory
        Timer {
            property int notificationId
            repeat: false
            onTriggered: root.expire(notificationId)
        }
    }

    // Do not instantiate a NotificationServer in previews: constructing it
    // claims org.freedesktop.Notifications from the current desktop.
    LazyLoader {
        active: root.enabled
        component: Component {
            N.NotificationServer {
                keepOnReload: true
                persistenceSupported: true
                bodySupported: true
                bodyMarkupSupported: false
                bodyHyperlinksSupported: false
                bodyImagesSupported: false
                actionsSupported: true
                imageSupported: false
                onNotification: notification => root.accept(notification)
            }
        }
    }
}
