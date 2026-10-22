import QtQuick
import Quickshell
import "../../shell/config" as C
import "../../shell/services" as S

ShellRoot {
    id: smoke
    property int phase: 0
    property var sample: null
    property var initialTime: null

    function signal() {
        return {callbacks: [], connect: function(callback) { this.callbacks.push(callback); }, emit: function() { for (const callback of this.callbacks) callback(); }};
    }
    function notification(id) {
        const item = {
            id: id, appName: "Test", appIcon: "", summary: "Original", body: "Body", urgency: 1,
            tracked: false, expireTimeout: 0, transient: false, lastGeneration: false,
            actions: [{text: "Original action", textChanged: signal(), invoke: function() {}}],
            closed: signal(), summaryChanged: signal(), bodyChanged: signal(), actionsChanged: signal(), expireTimeoutChanged: signal()
        };
        item.dismiss = function() { item.closed.emit(); };
        item.expire = function() { item.closed.emit(); };
        return item;
    }
    function check(value, message) {
        if (!value) { console.error("NOTIFICATION_REGRESSION", message); Qt.exit(1); }
    }

    Timer {
        interval: 150
        repeat: true
        running: true
        onTriggered: {
            if (smoke.phase === 0) {
                C.Settings.setValue("dnd", false);
                smoke.sample = smoke.notification(41);
                S.Notifications.accept(smoke.sample);
                smoke.initialTime = S.Notifications.history[0].time;
                S.Notifications.accept(smoke.sample);
                smoke.check(smoke.sample.closed.callbacks.length === 1, "duplicate close callback");
                smoke.check(smoke.sample.summaryChanged.callbacks.length === 1, "duplicate update callback");
                smoke.check(smoke.sample.actions[0].textChanged.callbacks.length === 1, "duplicate action callback");
                smoke.sample.summary = "Replacement";
                smoke.sample.body = "Replacement body";
                smoke.sample.expireTimeout = 450;
                smoke.sample.actions[0].text = "Replacement action";
                smoke.sample.summaryChanged.emit();
                smoke.sample.bodyChanged.emit();
                smoke.sample.expireTimeoutChanged.emit();
                smoke.sample.actions[0].textChanged.emit();
            } else if (smoke.phase === 1) {
                const entry = S.Notifications.history[0];
                smoke.check(entry.summary === "Replacement" && entry.body === "Replacement body", "snapshot did not refresh");
                smoke.check(entry.actions[0] === "Replacement action", "action text did not refresh");
                smoke.check(entry.time.getTime() === smoke.initialTime.getTime() && S.Notifications.unread === 1, "replacement changed age or unread count");
                smoke.check(S.Notifications.expiryTimers[41].interval === 450, "expiry did not restart in milliseconds");
                smoke.sample.actions[0].text = "Text-only update";
                smoke.sample.actions[0].textChanged.emit();
            } else if (smoke.phase === 2) {
                smoke.check(S.Notifications.history[0].actions[0] === "Text-only update", "standalone action text update lost");
                S.Notifications.clear();
                const restored = smoke.notification(42);
                restored.lastGeneration = true;
                S.Notifications.accept(restored);
                smoke.check(S.Notifications.active.length === 0 && S.Notifications.unread === 0, "reload re-toasted old notification");
                const transient = smoke.notification(43);
                transient.transient = true;
                S.Notifications.accept(transient);
                smoke.check(S.Notifications.history.some(entry => entry.id === 43), "active transient was not shown");
                transient.expire();
                smoke.check(!S.Notifications.history.some(entry => entry.id === 43), "closed transient persisted");
                smoke.check(S.Notifications.unread === 0, "transient left unread badge");
                const timed = smoke.notification(44);
                timed.expireTimeout = 50;
                S.Notifications.accept(timed);
            } else {
                const expired = S.Notifications.history.find(entry => entry.id === 44);
                smoke.check(expired && !expired.popup && expired.actions.length === 0, "real Timer did not expire notification");
                smoke.check(!S.Notifications.live[44] && !S.Notifications.expiryTimers[44], "expired live state leaked");
                S.Notifications.markRead();
                smoke.check(S.Notifications.unread === 0, "markRead failed");
                S.Notifications.clear();
                console.info("SUMI_NOTIFICATION_UPDATES_OK");
                Qt.quit();
            }
            smoke.phase += 1;
        }
    }
}
