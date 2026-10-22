pragma Singleton

import QtQuick
import Quickshell

Singleton {
    id: root

    readonly property string fallback: Qt.resolvedUrl("../assets/icons/grid.svg").toString()
    property int revision: 0
    Connections {
        target: DesktopEntries
        function onApplicationsChanged() { root.revision++; }
    }

    function identities(value): var {
        if (!value) return [];
        if (typeof value === "string") return [value.trim()].filter(id => id.length > 0);
        const ipc = value.lastIpcObject || {};
        const wayland = value.wayland || value.handle;
        const values = [wayland && wayland.appId, value.appId, ipc.class, ipc.initialClass];
        const result = [];
        for (const item of values) {
            const id = String(item || "").trim();
            if (id && result.indexOf(id) === -1) result.push(id);
        }
        // A webapp identity is more specific than a browser's generic app id.
        return result.filter(id => /(?:[a-p]{32}|^crx_)/i.test(id))
            .concat(result.filter(id => !/(?:[a-p]{32}|^crx_)/i.test(id)));
    }

    function appId(value): string { return identities(value)[0] || ""; }

    function candidates(value): var {
        const result = [];
        for (const raw of identities(value)) {
            const id = raw.replace(/\.desktop$/i, "").split("/").pop();
            if (id && result.indexOf(id) === -1) result.push(id);
            const webapp = /^(brave|chrome|chromium)-(?:webapp-)?([a-p]{32})(?:-(.+))?$/i.exec(id);
            if (webapp) {
                for (const alternate of [webapp[1] + "-" + webapp[2] + "-" + (webapp[3] || "Default"), "crx_" + webapp[2]])
                    if (result.indexOf(alternate) === -1) result.push(alternate);
            }
        }
        return result;
    }

    function aliases(id): var {
        const key = id.toLowerCase();
        if (/^brave(?:-|$)/.test(key) || key === "com.brave.browser")
            return ["brave-browser", "com.brave.Browser", "brave-desktop", "brave"];
        if (["kitty", "org.kitty_terminal.kitty"].indexOf(key) !== -1)
            return ["kitty", "org.kitty_terminal.kitty"];
        if (["zen", "zen-browser", "app.zen_browser.zen"].indexOf(key) !== -1)
            return ["zen", "zen-browser", "app.zen_browser.zen"];
        if (["thunar", "org.xfce.thunar"].indexOf(key) !== -1)
            return ["thunar", "org.xfce.thunar"];
        if (["chromium", "chromium-browser", "org.chromium.chromium"].indexOf(key) !== -1)
            return ["chromium", "chromium-browser", "org.chromium.Chromium"];
        return [];
    }

    function desktopEntry(value): var {
        // Native lookup methods are not properties. Reading revision keeps
        // callers' QML bindings subscribed to desktop-file index changes.
        const indexRevision = root.revision;
        const ids = candidates(value);
        for (const id of ids) {
            const entry = DesktopEntries.byId(id) || DesktopEntries.heuristicLookup(id);
            if (entry) return entry;
        }
        for (const id of ids) {
            for (const alias of aliases(id)) {
                const entry = DesktopEntries.byId(alias) || DesktopEntries.heuristicLookup(alias);
                if (entry) return entry;
            }
        }
        return null;
    }

    function iconUrl(icon): string {
        const name = String(icon || "").trim();
        if (!name) return "";
        // Keep provider queries and file/resource URLs intact. Theme names and
        // absolute paths are checked by Qt before accepting their provider URL.
        if (/^[a-z][a-z0-9+.-]*:/i.test(name)) return name;
        return Quickshell.iconPath(name, true) || "";
    }

    function appIcon(value): string {
        const entry = desktopEntry(value);
        const resolved = entry ? iconUrl(entry.icon) : "";
        if (resolved) return resolved;
        for (const id of candidates(value)) {
            const direct = iconUrl(id);
            if (direct) return direct;
            for (const alias of aliases(id)) {
                const icon = iconUrl(alias);
                if (icon) return icon;
            }
        }
        return root.fallback;
    }

    function displayName(value): string {
        const entry = desktopEntry(value);
        return entry && entry.name ? entry.name : appId(value) || "Application";
    }
}
