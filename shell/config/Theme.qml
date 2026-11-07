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
    readonly property color bgPanel: glassInset
    readonly property color bgPanelStrong: glassFill
    readonly property color bgPlaying: color("bgPlaying", "#49333e")
    readonly property color desktopBackground: color("desktopBackground", "#17151d")
    // Keep the dimmer below the compositor's .55 overlay blur cutoff.
    readonly property color scrim: {
        const value = color("scrim", "#88050911");
        return Qt.rgba(value.r, value.g, value.b, Math.min(value.a, 0.533));
    }
    readonly property color borderSoft: color("borderSoft", "#44c9aab8")
    readonly property color islandOutline: "#606066"
    readonly property color borderStrong: color("borderStrong", "#887e6176")
    readonly property color borderAccent1: color("borderAccent1", "#dc9eae")
    readonly property color borderAccent2: color("borderAccent2", "#e9ba97")
    readonly property color textMain: legibleOnGlass(color("textMain", "#f3e9df"))
    readonly property color textSoft: legibleOnGlass(color("textSoft", "#c4b4bd"))
    readonly property color accentBlue: legibleOnGlass(color("accentBlue", "#b8b5d9"))
    readonly property color accentCyan: legibleOnGlass(color("accentCyan", "#b8cac6"))
    readonly property color accentPink: legibleOnGlass(color("accentPink", "#dc9eae"))
    readonly property color accentWarn: legibleOnGlass(color("accentWarn", "#e9ba97"))
    // Derive the material from each wallpaper's palette, independently of old
    // almost-opaque theme alphas. Bound the tint so text also works over white.
    readonly property color glassFill: Qt.rgba(Math.min(0.12, desktopBackground.r * 0.78),
        Math.min(0.12, desktopBackground.g * 0.78), Math.min(0.12, desktopBackground.b * 0.78), 0.70)
    readonly property color glassInset: Qt.rgba(desktopBackground.r, desktopBackground.g, desktopBackground.b, 0.16)
    readonly property color glassRim: Qt.rgba(1, 1, 1, 0.26)
    readonly property color glassHighlight: Qt.rgba(1, 1, 1, 0.07)
    readonly property string font: typography.font || "Adwaita Sans"
    readonly property string fontMono: typography.fontMono || "JetBrains Mono"
    readonly property int fontSize: typography.fontSize || 13
    readonly property color barBackground: glassFill
    readonly property int barHeight: 34
    readonly property int panelTop: 56
    readonly property int windowRounding: dimensions.windowRounding === undefined ? 20 : dimensions.windowRounding
    readonly property int borderWidth: dimensions.borderWidth === undefined ? 1 : dimensions.borderWidth

    function color(key: string, fallback: string): color {
        return root.colors[key] || fallback;
    }

    function luminance(value): real {
        const linear = channel => channel <= 0.04045 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4);
        return linear(value.r) * 0.2126 + linear(value.g) * 0.7152 + linear(value.b) * 0.0722;
    }

    function legibleOnGlass(foreground): color {
        // Include the brightest sheen and white wallpaper. Blur changes detail,
        // not this worst-case luminance, so the check also holds without blur.
        const body = root.glassFill;
        const sheen = root.glassHighlight.a;
        const backdrop = Qt.rgba((body.r * body.a + 1 - body.a) * (1 - sheen) + sheen,
            (body.g * body.a + 1 - body.a) * (1 - sheen) + sheen,
            (body.b * body.a + 1 - body.a) * (1 - sheen) + sheen, 1);
        const background = luminance(backdrop);
        let value = foreground;
        for (let step = 0; step < 32; step++) {
            if ((luminance(value) + 0.05) / (background + 0.05) >= 4.55) return value;
            value = Qt.rgba(value.r + (1 - value.r) * 0.12,
                value.g + (1 - value.g) * 0.12, value.b + (1 - value.b) * 0.12, 1);
        }
        return "#ffffff";
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
