import QtQuick
import Quickshell
import Quickshell.Io

Scope {
    id: root
    property var argv: []
    property string label: ""
    property var callback: null
    property string operationId: ""
    property double deadline: 0
    property int readFailures: 0
    property bool completed: false
    property int timeoutMs: 180000
    signal finished(bool ok, var result, string error)

    function start(): void {
        deadline = Date.now() + timeoutMs;
        watchdog.start();
        if (operationId) { poll.start(); return; }
        command.command = [Desktop.controller].concat(argv.map(String));
        command.running = true;
    }
    function finish(ok, result, error): void {
        if (completed) return;
        completed = true;
        poll.stop();
        watchdog.stop();
        command.running = false;
        statusRead.running = false;
        finished(ok, result, error);
        Qt.callLater(() => root.destroy());
        try { if (typeof callback === "function") callback(ok, result, error); }
        catch (callbackError) { console.warn("Sumi action callback:", String(callbackError)); }
    }
    function decode(text) { try { return JSON.parse(text); } catch (error) { return {}; } }
    Timer {
        id: watchdog
        interval: 250
        repeat: true
        onTriggered: {
            if (Date.now() >= root.deadline) {
                root.finish(false, {}, root.operationId ? "The desktop change is still pending. Check desktopctl operation status " + root.operationId + "." : "The action timed out. Try again.");
            } else if (!root.operationId && !command.running && Date.now() > root.deadline - root.timeoutMs + 1000) {
                root.finish(false, {}, "Could not start the desktop controller. Check desktopctl doctor.");
            }
        }
    }
    Process {
        id: command
        stdout: StdioCollector { id: output }
        stderr: StdioCollector { id: errors }
        onExited: (code, status) => {
            if (root.completed) return;
            const value = root.decode(output.text);
            if (code !== 0) { root.finish(false, value, errors.text.trim() || "Could not complete " + root.label + "."); return; }
            if (value.operation_id) {
                root.operationId = value.operation_id;
                poll.start();
            } else root.finish(true, value, "");
        }
    }
    Timer {
        id: poll
        interval: 300
        onTriggered: {
            if (Date.now() > root.deadline) { root.finish(false, {}, "The change is still pending. Check desktopctl operation status " + root.operationId + "."); return; }
            statusRead.command = [Desktop.controller, "operation", "status", root.operationId, "--json"];
            statusRead.running = true;
        }
    }
    Process {
        id: statusRead
        stdout: StdioCollector { id: operationOutput }
        stderr: StdioCollector { id: operationErrors }
        onExited: (code, status) => {
            if (root.completed) return;
            const value = root.decode(operationOutput.text);
            if (code !== 0) {
                if (++root.readFailures < 3) poll.start();
                else root.finish(false, value, operationErrors.text.trim() || "Could not read the change result.");
            } else if (value.status === "succeeded") root.finish(true, value.result || value, "");
            else if (value.status === "failed") root.finish(false, value, value.error || "The desktop change failed and was restored.");
            else { root.readFailures = 0; poll.start(); }
        }
    }
}
