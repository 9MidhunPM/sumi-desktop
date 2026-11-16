pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Hyprland

Singleton {
    // Quickshell forwards dispatch strings verbatim. Lua sessions require a
    // dispatcher expression, not the legacy hyprlang command spelling.
    function focusWorkspace(value: var): void {
        if (Desktop.preview) return;
        const name = String(value);
        if (!name.length) return;
        if (name.indexOf("special:") === 0) {
            const special = name.slice(8);
            Hyprland.dispatch(Hyprland.usingLua
                ? "hl.dsp.workspace.toggle_special(" + JSON.stringify(special) + ")"
                : "togglespecialworkspace " + special);
        } else {
            Hyprland.dispatch(Hyprland.usingLua
                ? "hl.dsp.focus({ workspace = " + JSON.stringify(name) + " })"
                : "workspace " + name);
        }
    }

    function windowAddress(address: string): string {
        const value = String(address || "");
        return /^(?:0x)?[0-9a-f]+$/i.test(value) ? "0x" + value.replace(/^0x/i, "") : "";
    }

    function focusWindow(address: string): void {
        const normalized = windowAddress(address);
        if (Desktop.preview || !normalized) return;
        Hyprland.dispatch(Hyprland.usingLua
            ? "hl.dsp.focus({ window = " + JSON.stringify("address:" + normalized) + " })"
            : "focuswindow address:" + normalized);
    }

    // Move without switching away from the overview or changing focus.
    function moveWindowToWorkspace(address: string, value: var): void {
        const normalized = windowAddress(address);
        if (Desktop.preview || !normalized) return;
        const name = String(value);
        // Legacy dispatch separates its workspace and window selectors with a
        // comma; disallow separator/control characters in both modes.
        if (!name.length || /[,\r\n\x00]/.test(name)) return;
        Hyprland.dispatch(Hyprland.usingLua
            ? "hl.dsp.window.move({ window = " + JSON.stringify("address:" + normalized)
                + ", workspace = " + JSON.stringify(name) + ", follow = false })"
            : "movetoworkspacesilent " + name + ",address:" + normalized);
    }
}
