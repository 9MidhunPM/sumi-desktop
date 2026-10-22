pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root
    readonly property string controller: Quickshell.env("SUMI_DESKTOPCTL") || "desktopctl"
    readonly property bool preview: Quickshell.env("SUMI_PREVIEW") === "1"
    property string lastAction: ""
    property string lastError: ""
    property int pendingCount: 0
    signal completed(string action, bool ok, var result, string error)

    Component { id: requestFactory; ControllerRequest {} }
    function watchOperation(id: string): void {
        const request = requestFactory.createObject(root, {operationId: id, label: "desktop change"});
        if (!request) return;
        root.pendingCount += 1;
        request.finished.connect(function(ok, result, error) {
            root.pendingCount = Math.max(0, root.pendingCount - 1);
            root.lastError = ok ? "" : error;
            root.completed("desktop change", ok, result, error);
        });
        request.start();
    }
    // The independent controller can outlive the shell which requested it.
    // Discover its durable receipt after a restart, even if the queued response
    // never reached the previous shell.
    Process {
        id: recovery
        command: [root.controller, "operation", "status", "latest", "--json"]
        running: !root.preview
        stdout: StdioCollector { id: latest }
        stderr: StdioCollector {}
        onExited: (code, status) => {
            if (code !== 0) return;
            try {
                const value = JSON.parse(latest.text);
                if (value.status === "queued" || value.status === "running") root.watchOperation(value.operation_id || value.id);
                else if (value.status === "failed") root.lastError = value.error || "The previous desktop change failed.";
            } catch (error) { console.warn("Sumi: could not read the previous operation result"); }
        }
    }
    function run(argv: var, label: string, callback: var): void {
        root.lastAction = label;
        root.lastError = "";
        if (preview) {
            console.info("Sumi preview action:", label, JSON.stringify(argv));
            if (typeof callback === "function") callback(false, {preview: true}, "Preview · desktop changes are disabled");
            return;
        }
        const request = requestFactory.createObject(root, {argv: argv, label: label, callback: callback || null});
        if (!request) {
            root.lastError = "Could not start " + label + ".";
            root.completed(label, false, {}, root.lastError);
            if (typeof callback === "function") callback(false, {}, root.lastError);
            return;
        }
        root.pendingCount += 1;
        request.finished.connect(function(ok, result, error) {
            root.pendingCount = Math.max(0, root.pendingCount - 1);
            root.lastError = ok ? "" : error;
            root.completed(label, ok, result, error);
        });
        request.start();
    }

    // Arguments remain an argv array. Never route launcher text through a shell.
    function action(command: string, args: var, callback: var): void {
        const parameters = args || [];
        run(["action", command].concat(parameters.map(String)), command, callback);
    }

    function theme(id: string): void {
        run(["theme", "use", id], "theme", null);
    }

    function profile(id: string): void {
        run(["profile", "use", id], "profile", null);
    }
}
