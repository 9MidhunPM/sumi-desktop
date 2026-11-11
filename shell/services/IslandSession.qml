import QtQuick

// Navigation lives above the native windows: closing or moving the desk never
// destroys its route. Secrets such as network passwords stay in their page.
QtObject {
    id: root
    property string route: "controls"
    property string entityId: ""
    property var history: []
    property int revision: 0
    property var savedPages: ({})
    readonly property var destinations: ["home", "inbox", "media", "controls", "thursday", "desktop"]
    readonly property var routes: ["home", "calendar", "inbox", "notification", "media", "controls", "wifi", "bluetooth", "audio", "capture", "system", "power", "settings", "pomodoro", "thursday", "desktop", "launcher", "files", "clipboard", "appearance", "widgets", "codex", "help"]

    function destinationFor(value) {
        if (["calendar"].indexOf(value) >= 0) return "home";
        if (value === "notification") return "inbox";
        if (["wifi", "bluetooth", "audio", "capture", "system", "power", "settings", "pomodoro"].indexOf(value) >= 0) return "controls";
        if (["launcher", "files", "clipboard", "appearance", "widgets", "codex", "help"].indexOf(value) >= 0) return "desktop";
        return destinations.indexOf(value) >= 0 ? value : "home";
    }
    function navigate(value, entity = "", reason = "push") {
        if (routes.indexOf(value) < 0) return false;
        value = value === "home" ? "controls" : value === "desktop" ? "launcher" : value;
        const nextEntity = String(entity || "");
        if (value === route && nextEntity === entityId && reason !== "fresh") return true;
        if (value === "controls") history = [];
        else if (reason === "fresh") history = [{route: "controls", entityId: ""}];
        else if (value !== route || nextEntity !== entityId)
            history = history.concat([{route: route, entityId: entityId}]);
        route = value;
        entityId = nextEntity;
        revision++;
        return true;
    }
    function back() {
        if (!history.length) return false;
        const entries = history.slice();
        const previous = entries.pop();
        history = entries;
        route = previous.route;
        entityId = previous.entityId;
        revision++;
        return true;
    }
    function save(key, value) {
        const next = Object.assign({}, savedPages);
        next[key] = value;
        savedPages = next;
    }
}
