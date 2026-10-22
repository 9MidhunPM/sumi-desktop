pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root
    readonly property string stateDir: Quickshell.env("SUMI_STATE_DIR") || ((Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state")) + "/sumi")
    property bool barHiddenMode: false
    property bool reducedMotion: false
    property bool fullMotion: false
    property bool dnd: false
    property string error: ""
    property bool loading: true

    function setValue(key: string, value: bool): void {
        if (["barHiddenMode", "reducedMotion", "fullMotion", "dnd"].indexOf(key) < 0)
            return;
        root[key] = value;
        save();
    }

    function toggle(key: string): void {
        setValue(key, !root[key]);
    }

    function cycleMotion(): void {
        if (reducedMotion) { reducedMotion = false; fullMotion = false; }
        else if (fullMotion) { reducedMotion = true; fullMotion = false; }
        else fullMotion = true;
        save();
    }

    function save(): void {
        if (Quickshell.env("SUMI_PREVIEW") === "1")
            return;
        settingsFile.setText(JSON.stringify({version: 1, barHiddenMode: root.barHiddenMode, reducedMotion: root.reducedMotion, fullMotion: root.fullMotion, dnd: root.dnd}, null, 2) + "\n");
    }

    function load(): void {
        try {
            const settings = JSON.parse(settingsFile.text());
            for (const key of ["barHiddenMode", "reducedMotion", "fullMotion", "dnd"])
                if (typeof settings[key] === "boolean") root[key] = settings[key];
            root.error = "";
        } catch (error) {
            root.error = "Settings could not be read; using the current settings.";
        }
        root.loading = false;
    }

    FileView {
        id: settingsFile
        path: root.stateDir + "/settings.json"
        preload: true
        printErrors: false
        watchChanges: true
        atomicWrites: true
        onLoaded: root.load()
        onLoadFailed: root.loading = false
        onSaveFailed: root.error = "Settings could not be saved. Check the Sumi state directory."
        onSaved: root.error = ""
        onFileChanged: reload()
    }
}
