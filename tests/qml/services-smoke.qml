import QtQuick
import Quickshell
import "../../shell/config" as C
import "../../shell/services" as S

ShellRoot {
    Component.onCompleted: console.info("SUMI_SERVICE_INIT", C.Theme.name, C.Settings.barHiddenMode)
    // The Python runner copies this beside config/ and services/ because
    // Quickshell's VFS confines imports to a configuration's root directory.
    Timer {
        interval: 500
        running: true
        onTriggered: {
            const checks = [
                C.Theme.name.length > 0,
                C.Theme.font.length > 0,
                C.Theme.fontSize > 0,
                typeof C.Settings.barHiddenMode === "boolean",
                S.Desktop.preview === true,
                S.Notifications.enabled === false,
                S.Notifications.count === 0,
                S.Audio.volume >= 0,
                S.Battery.percent >= 0,
                S.Media.title.length > 0,
                S.Network.name.length > 0,
                typeof S.Bluetooth.enabled === "boolean",
                S.Clock.time.length > 0,
                S.Notifications.plain("<b>Hello</b> &amp; world") === "Hello & world"
            ];
            if (Quickshell.env("SUMI_TEST_FIXTURE") === "1") {
                checks.push(C.Theme.name === "Fixture Theme");
                checks.push(C.Theme.font === "Test Sans");
                checks.push(C.Theme.fontMono === "Test Mono");
                checks.push(C.Theme.fontSize === 16);
                checks.push(C.Theme.windowRounding === 11);
                checks.push(C.Theme.borderWidth === 3);
                checks.push(C.Settings.barHiddenMode === true);
                checks.push(C.Settings.dnd === true);
            }
            let invoked = false;
            let onClose = function() {};
            const sample = {
                id: 91, tracked: false, appName: "<b>Example</b>",
                summary: "Safe &amp; clear", body: "<script>text</script>",
                appIcon: "", urgency: 1, expireTimeout: 0,
                actions: [{text: "Open", invoke: function() { invoked = true; }}],
                closed: {connect: function(callback) { onClose = callback; }},
                dismiss: function() { onClose(); }, expire: function() { onClose(); }
            };
            S.Notifications.accept(sample);
            checks.push(sample.tracked === true);
            checks.push(S.Notifications.history[0].appName === "Example");
            checks.push(S.Notifications.history[0].summary === "Safe & clear");
            S.Notifications.invoke(91, 0);
            checks.push(invoked);
            S.Notifications.expire(91);
            checks.push(S.Notifications.history[0].popup === false);
            checks.push(S.Notifications.history[0].actions.length === 0);
            S.Notifications.clear();
            checks.push(S.Notifications.count === 0 && S.Notifications.unread === 0);
            if (checks.some(value => !value)) {
                console.error("SUMI_SERVICES_SMOKE_FAILED", JSON.stringify(checks));
                Qt.exit(1);
            } else {
                console.info("SUMI_SERVICES_SMOKE_OK", C.Theme.name, S.Clock.time, S.Network.name);
                Qt.quit();
            }
        }
    }
}
