pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

// The controller writes a complete theme atomically. Keep the last valid theme
// while an editor or a failed import leaves an invalid document on disk.
Singleton {
    id: root
    readonly property string stateDir: Quickshell.env("SUMI_STATE_DIR") || ((Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state")) + "/sumi")
    property var document: ({})
    readonly property var colors: document.colors || ({})
    readonly property var typography: document.typography || document
    readonly property var dimensions: document.dimensions || document
    readonly property string id: document.id || "japanese-sunset"
    readonly property string name: document.name || "Japanese Sunset"
    readonly property string wallpaper: document.wallpaper || ""
    readonly property bool reducedMotion: Motion.reduced
    readonly property bool effectiveReducedMotion: Motion.reduced
    readonly property bool batteryMotion: Motion.battery
    readonly property bool expressiveMotion: Motion.expressive
    readonly property int motionEnter: Motion.enter
    readonly property int motionExit: Motion.exit
    readonly property int motionControl: Motion.control
    readonly property color bgPanel: color("bgPanel", "#e51c1b23")
    readonly property color bgPanelStrong: color("bgPanelStrong", "#f51c1b23")
    readonly property color bgPlaying: color("bgPlaying", "#49333e")
    readonly property color desktopBackground: color("desktopBackground", "#17151d")
    readonly property color scrim: color("scrim", "#88050911")
    readonly property color borderSoft: color("borderSoft", "#44c9aab8")
    readonly property color borderStrong: color("borderStrong", "#887e6176")
    readonly property color borderAccent1: color("borderAccent1", "#dc9eae")
    readonly property color borderAccent2: color("borderAccent2", "#e9ba97")
    readonly property color textMain: color("textMain", "#f3e9df")
    readonly property color textSoft: color("textSoft", "#c4b4bd")
    readonly property color accentBlue: color("accentBlue", "#b8b5d9")
    readonly property color accentCyan: color("accentCyan", "#b8cac6")
    readonly property color accentPink: color("accentPink", "#dc9eae")
    readonly property color accentWarn: color("accentWarn", "#e9ba97")
    readonly property string font: typography.font || "Adwaita Sans"
    readonly property string fontMono: typography.fontMono || "JetBrains Mono"
    readonly property int fontSize: typography.fontSize || 13
    readonly property color barBackground: Qt.rgba(desktopBackground.r, desktopBackground.g, desktopBackground.b, 0.62)
    readonly property int barHeight: 34
    readonly property int panelTop: 56
    readonly property int windowRounding: dimensions.windowRounding === undefined ? 20 : dimensions.windowRounding
    readonly property int borderWidth: dimensions.borderWidth === undefined ? 1 : dimensions.borderWidth

    function color(key: string, fallback: string): color {
        return root.colors[key] || fallback;
    }

    function loadTheme(): void {
        try {
            const candidate = JSON.parse(themeFile.text());
            if (candidate && candidate.colors && typeof candidate.colors === "object")
                root.document = candidate;
        } catch (error) {
            console.warn("Sumi: keeping last valid theme:", String(error));
        }
    }

    FileView {
        id: themeFile
        path: root.stateDir + "/theme.json"
        preload: true
        printErrors: false
        watchChanges: true
        onLoaded: root.loadTheme()
        onFileChanged: reload()
    }
}
