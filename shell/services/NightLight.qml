pragma Singleton

import QtQuick
import Quickshell

Singleton {
    id: root
    property bool available: false
    property bool active: false
    property bool busy: false
    property bool loading: false
    property string error: ""
    property int serial: 0

    function refresh(preserveError = false): void {
        if (Desktop.preview || busy || loading) return;
        const request = ++serial;
        loading = true;
        busy = true;
        Desktop.action("night-light-get", [], function(ok, result, detail) {
            root.loading = false;
            root.busy = false;
            if (request !== root.serial) return;
            root.available = ok && result.available === true;
            if (ok) { root.active = result.active === true; if (!preserveError) root.error = ""; }
            else root.error = detail || "Night light is unavailable.";
        });
    }
    function toggle(): void {
        if (Desktop.preview || !available || busy) return;
        ++serial;
        busy = true;
        error = "";
        Desktop.action("night-light", [], function(ok, result, detail) {
            root.busy = false;
            if (ok) { root.available = result.available === true; root.active = result.active === true; }
            else { root.error = detail || "Could not change night light."; root.refresh(true); }
        });
    }
}
