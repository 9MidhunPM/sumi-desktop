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

    function focusWindow(address: string): void {
        if (Desktop.preview || !/^0x[0-9a-f]+$/i.test(address)) return;
        Hyprland.dispatch(Hyprland.usingLua
            ? "hl.dsp.focus({ window = " + JSON.stringify("address:" + address) + " })"
            : "focuswindow address:" + address);
    }
}
