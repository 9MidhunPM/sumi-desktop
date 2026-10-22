#!/usr/bin/env python3
"""Exercise real desktop cards, crop-aware placement, motion and demand gates."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw


HARNESS = r'''import QtQuick
import QtTest
import Quickshell
import "config"
import "services" as S
import "widgets/WidgetLayout.js" as Layout
ShellRoot {
    id: testRoot
    property var themes: THEMES_JSON
    QtObject { id: screenInfo; property string name: "eDP-1"; property int width: 1920; property int height: 1080 }
    QtObject {
        id: fakeApp
        property var widgetScreen: screenInfo
        property string lastPanel: ""
        function open(name, screen) { lastPanel = name; }
    }
    QtObject {
        id: spotify
        property string dbusName: "org.mpris.MediaPlayer2.spotify.instance2"
        property string desktopEntry: "spotify"
        property string identity: "Spotify"
        property string trackTitle: "A quiet place to begin"
        property string trackArtist: "Your soundtrack"
        property string trackArtUrl: Qt.resolvedUrl("fixture-art.svg")
        property bool isPlaying: true
        property bool canGoPrevious: true
        property bool canGoNext: true
        property bool canTogglePlaying: true
        property bool canRaise: true
        property bool lengthSupported: true
        property bool positionSupported: true
        property real length: 240
        property real position: 92
        signal trackChanged()
    }
    QtObject {
        id: browser
        property string dbusName: "org.mpris.MediaPlayer2.chromium"
        property string desktopEntry: "brave-browser"
        property string identity: "Brave"
        property string trackTitle: "Browser player"
        property string trackArtist: "A different source"
        property string trackArtUrl: ""
        property bool isPlaying: true
    }
    DesktopWidgets { id: widgets; modelData: screenInfo; app: fakeApp }
    TestCase {
        name: "SumiDesktopWidgets"
        when: widgets.visible
        function check(value, message) {
            if (!value) { console.error("SUMI_WIDGETS_FAILED", message); Qt.exit(1); throw new Error(message); }
        }
        function ready(condition, message) {
            let elapsed = 0;
            while (!condition() && elapsed < 4000) { wait(20); elapsed += 20; }
            check(condition(), message);
        }
        function card(key) { return findChild(widgets.contentItem, "desktop" + key[0].toUpperCase() + key.slice(1)); }
        function luminance(color) {
            const c = value => value <= 0.04045 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4);
            return 0.2126*c(color.r) + 0.7152*c(color.g) + 0.0722*c(color.b);
        }
        function assertCardContrast(theme) {
            const panel = card("spotify");
            const bg = panel.panelColor;
            const composite = Qt.rgba(bg.r*bg.a+1-bg.a, bg.g*bg.a+1-bg.a, bg.b*bg.a+1-bg.a, 1);
            const b = luminance(composite);
            for (const color of [panel.mainText,panel.secondaryText,panel.warningText]) {
                const f = luminance(color);
                check((Math.max(f,b)+0.05)/(Math.min(f,b)+0.05) >= 4.5, theme.id + " card text readable over white wallpaper detail");
            }
        }
        function scene(theme) {
            return {version: 1, imageKey: theme.id, wallpaper: theme.wallpaper,
                sourceSize: theme.sourceSize, layout: theme.desktopLayout};
        }
        function setMode(mode) {
            const next = JSON.parse(JSON.stringify(S.Widgets.document));
            next.layouts = mode === "curated" ? {} : {[S.Widgets.scene.imageKey]: mode};
            S.Widgets.document = next;
        }
        function bounds(label) {
            const names = ["clock", "spotify", "priorities", "deadline"];
            const geo = widgets.geometry;
            names.forEach(key => {
                const r = geo[key];
                check(Number.isFinite(r.x) && Number.isFinite(r.y) && r.width > 0 && r.height > 0, label + " finite " + key);
                check(r.x >= -0.01 && r.y >= 48 && r.x + r.width <= widgets.width + 0.01 && r.y + r.height <= widgets.height + 0.01, label + " bounded " + key);
                const item = card(key);
                check(item && Math.abs(item.x - r.x) < 0.1 && Math.abs(item.y - r.y) < 0.1, label + " actual placement " + key);
            });
            for (let a = 0; a < names.length; a++) for (let b = a + 1; b < names.length; b++)
                check(!Layout.intersects(geo[names[a]], geo[names[b]], 0), label + " no overlap " + names[a] + "/" + names[b]);
        }
        function test_cards() {
            ready(() => S.Widgets.loaded && widgets.initialized, "Widgets initialized");
            Settings.reducedMotion = true;
            S.Media.players = [browser, spotify];
            S.Media.selectedBus = browser.dbusName;
            const data = S.Widgets.defaults();
            data.priorities = [{text: "One important thing", done: false}, {text: "Make time to learn", done: false}, {text: "A little space for yourself", done: true}];
            data.deadline = {title: "Something to look forward to", at: S.Clock.date.getTime() + 3 * 86400000 + 7 * 3600000};
            S.Widgets.document = data;
            ready(() => S.WidgetMedia.player === spotify && widgets.artworkSource.length > 0, "Spotify metadata and art selected");
            check(S.Media.player === browser, "Desktop Spotify selection preserves the bar's player");
            check(findChild(widgets.contentItem, "desktopSpotifyTitle").text === spotify.trackTitle, "Actual media card renders the selected Spotify title");
            check(findChild(widgets.contentItem, "desktopDeadlineValue").text === "3d 7h left", "Deadline has real minute-derived value");
            check(findChild(widgets.contentItem, "desktopPriority2").checked, "Priority completion is rendered");
            check(S.WidgetMedia.displayActive && S.WidgetMedia.progressActive, "Visible desktop has one progress consumer");
            findChild(widgets.contentItem, "desktopPrioritiesEdit").clicked();
            check(fakeApp.lastPanel === "widgets", "The edit control opens the existing overlay route");
            check(widgets.smokeMask.regions.length === 4, "Pointer mask contains only the four card regions");
            const centered = Layout.sourcePoint([0.5, 0.5], [3840, 2160], 1080, 1920);
            check(centered.x === 540 && centered.y === 960, "Portrait cover crop keeps the source center centered");
            let checked = 0;
            for (const theme of testRoot.themes) {
                Theme.document = theme;
                assertCardContrast(theme);
                S.Widgets.committedScene = scene(theme);
                for (const size of [[2304,1440],[1920,1080],[1280,720],[960,600],[600,480],[1080,1920]]) {
                    screenInfo.width = size[0]; screenInfo.height = size[1];
                    for (const mode of ["curated","left","right","split"]) {
                        setMode(mode); wait(1);
                        bounds(theme.id + " " + size + " " + mode);
                        checked++;
                    }
                }
            }
            check(checked === testRoot.themes.length * 24, "Every curated wallpaper and override checked");

            const disabled = JSON.parse(JSON.stringify(S.Widgets.document));
            disabled.enabled.spotify = false;
            S.Widgets.document = disabled; wait(1);
            check(!card("spotify").visible && widgets.smokeMask.regions[1].width === 0 && !S.WidgetMedia.displayActive, "Hidden Spotify card has no pointer area or media demand");
            S.Widgets.document = data; wait(1);

            screenInfo.width = 1920; screenInfo.height = 1080;
            S.Widgets.committedScene = scene(testRoot.themes[0]);
            setMode("left"); wait(2);
            Settings.reducedMotion = false;
            const clock = card("clock");
            const fromX = clock.x;
            setMode("right"); wait(60);
            check(clock.x > fromX && clock.x < widgets.geometry.clock.x, "Wallpaper layout moves through intermediate frames");
            setMode("left"); wait(80);
            setMode("right"); wait(700);
            check(Math.abs(clock.x - widgets.geometry.clock.x) < 0.1, "Rapid switches settle at the latest destination");
            screenInfo.width = 2304; screenInfo.height = 1440; wait(1);
            check(!widgets.moving && Math.abs(clock.x - widgets.geometry.clock.x) < 0.1, "Monitor geometry changes settle directly");
            screenInfo.width = 1920; screenInfo.height = 1080; wait(1);
            setMode("left"); wait(30);
            widgets.smokeIdle.isIdle = true; wait(1);
            check(!S.WidgetMedia.displayActive && !S.WidgetMedia.progressActive && widgets.moveDuration === 0, "Idle stops progress and movement");
            check(Math.abs(clock.x - widgets.geometry.clock.x) < 0.1, "Idle finishes a running movement " + clock.x + " vs " + widgets.geometry.clock.x);
            const rememberedArt = widgets.artworkSource;
            spotify.trackArtUrl = Qt.resolvedUrl("fixture-art-2.svg"); wait(1);
            check(widgets.artworkSource === rememberedArt, "Idle avoids starting new cover requests");
            widgets.smokeIdle.isIdle = false; wait(1);
            check(S.WidgetMedia.displayActive && widgets.artworkSource !== rememberedArt, "Activity resumes current metadata immediately");
            widgets.monitor = {activeWorkspace: {hasFullscreen: true}}; wait(1);
            check(!widgets.visible && !S.WidgetMedia.displayActive && !S.WidgetMedia.progressActive, "Fullscreen unmaps cards and releases media demand");
            setMode("right"); wait(1);
            check(Math.abs(clock.x - widgets.geometry.clock.x) < 0.1, "Hidden layout settles without animation");
            widgets.monitor = {activeWorkspace: {hasFullscreen: false, toplevels: {values: [{}, {}]}}}; wait(1);
            check(widgets.visible && S.WidgetMedia.displayActive, "Normal windows retain the desktop behind translucent content");
            fakeApp.widgetScreen = null; wait(1);
            check(!widgets.visible && !S.WidgetMedia.displayActive, "No chosen output releases all demand");
            fakeApp.widgetScreen = screenInfo; wait(1);
            Settings.reducedMotion = true;
            setMode("left"); wait(1);
            check(widgets.moveDuration === 0 && Math.abs(clock.x - widgets.geometry.clock.x) < 0.1, "Reduced motion is immediate");
            Settings.reducedMotion = false;
            Motion.battery = true;
            check(widgets.moveDuration === 140, "Adaptive battery relocation stays short");
            Motion.battery = false;
            check(widgets.moveDuration === 650, "Expressive relocation retains its intended glide");
            Settings.reducedMotion = true;
            const past = JSON.parse(JSON.stringify(S.Widgets.document));
            past.deadline.at = S.Clock.date.getTime() - 3600000;
            S.Widgets.document = past; wait(1);
            check(findChild(widgets.contentItem, "desktopDeadlineValue").text === "Overdue by 1h 0m", "Overdue deadline remains explicit");
            past.deadline.at = null;
            S.Widgets.document = JSON.parse(JSON.stringify(past)); wait(1);
            check(findChild(widgets.contentItem, "desktopDeadlineValue").text === "Set a deadline", "Unset deadline offers an honest empty state");
            S.Media.players = [browser]; wait(1);
            check(findChild(widgets.contentItem, "desktopSpotifyTitle").text === "A little music?", "Missing Spotify shows its empty state without using browser playback");
            S.Media.players = [browser, spotify];
            S.Widgets.document = data;
            for (const theme of testRoot.themes) {
                Theme.document = theme;
                S.Widgets.committedScene = scene(theme);
                setMode("curated");
                widgets.smokeWallpaper = theme.wallpaper;
                ready(() => widgets.smokeBackground.status === Image.Ready, "Wallpaper image ready " + theme.id);
                wait(30);
                grabImage(widgets.contentItem).save("/tmp/sumi-widgets-" + theme.id + ".png");
            }
            console.info("SUMI_WIDGETS_OK", checked, "layouts");
            // Clear fixture references before their QtObjects are destroyed;
            // real MPRIS models remove players before destroying them too.
            S.Media.players = []; wait(1);
            Qt.quit();
        }
    }
}
'''


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    themes = json.loads((repo / "assets/themes/catalog.json").read_text())["themes"]
    for theme in themes:
        theme["wallpaper"] = (repo / theme["wallpaper"]).as_uri()
    with tempfile.TemporaryDirectory(prefix="sumi-widgets-") as temporary:
        work = Path(temporary)
        # awww decodes real wallpaper files; some Qt builds lack the optional
        # WebP plugin. Decode only test backdrops to PNG, preserving the image.
        for theme in themes:
            if theme["wallpaper"].lower().endswith(".webp"):
                from urllib.parse import unquote, urlparse
                converted = work / (theme["id"] + ".png")
                with Image.open(unquote(urlparse(theme["wallpaper"]).path)) as backdrop:
                    backdrop.convert("RGB").save(converted)
                theme["wallpaper"] = converted.as_uri()
        config = work / "shell"
        shutil.copytree(repo / "shell", config)
        path = config / "DesktopWidgets.qml"
        source = path.read_text().replace("PanelWindow {", "Window {", 1)
        source = re.sub(r"^    (screen:|anchors \{|exclusiveZone:|exclusionMode:|WlrLayershell\.).*\n", "", source, flags=re.M)
        source = re.sub(r"^    readonly property var monitor:.*$", "    property var monitor: ({activeWorkspace: {hasFullscreen: false}})", source, flags=re.M)
        source = re.sub(r"^    IdleMonitor \{.*$", "    QtObject { id: idleMonitor; property bool isIdle: false }", source, flags=re.M)
        source = source.replace("    mask: Region {", "    readonly property var smokeMask: Region {")
        source = source.replace('    color: "transparent"', '''    width: modelData ? modelData.width : 1920
    height: modelData ? modelData.height : 1080
    property string smokeWallpaper: ""
    readonly property var smokeIdle: idleMonitor
    readonly property var smokeBackground: background
    Image { id: background; anchors.fill: parent; source: root.smokeWallpaper; fillMode: Image.PreserveAspectCrop; z: -100 }
    color: "transparent"''', 1)
        path.write_text(source)
        media = config / "services/Media.qml"
        media.write_text(media.read_text().replace("readonly property var players: Mp.Mpris.players.values", "property var players: []"))
        widgets = config / "services/Widgets.qml"
        widgets.write_text(widgets.read_text().replace("        running: true", "        running: false"))
        motion = config / "config/Motion.qml"
        motion.write_text(re.sub(r"^    readonly property bool battery:.*$", "    property bool battery: false", motion.read_text(), flags=re.M))
        for name, color in (("fixture-art.svg", "#679e98"), ("fixture-art-2.svg", "#af87a1")):
            (config / name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="216" height="216"><rect width="216" height="216" fill="#182b35"/><circle cx="108" cy="108" r="70" fill="{color}"/><circle cx="108" cy="108" r="22" fill="#182b35"/><circle cx="108" cy="108" r="5" fill="#eff1dd"/></svg>')
        (config / "shell.qml").write_text(HARNESS.replace("THEMES_JSON", json.dumps(themes)))
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, SUMI_PREVIEW="1", SUMI_STATE_DIR=str(work / "state"), SUMI_DESKTOPCTL=str(repo / "bin/desktopctl"), QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime))
        result = subprocess.run(["qs", "-p", str(config)], env=environment, capture_output=True, text=True, timeout=45)
        output = result.stdout + result.stderr
        if result.returncode or "SUMI_WIDGETS_OK" not in output or any(message in output for message in ("TypeError:", "ReferenceError:", "Failed to load configuration", "Unable to assign [undefined]", "FAIL!", "Binding loop")):
            raise SystemExit(output)
    columns = 4
    tile_width, tile_height, caption = 480, 270, 30
    rows = (len(themes) + columns - 1) // columns
    montage = Image.new("RGB", (columns * tile_width, rows * (tile_height + caption)), "#161720")
    draw = ImageDraw.Draw(montage)
    for index, theme in enumerate(themes):
        image_path = Path("/tmp") / ("sumi-widgets-" + theme["id"] + ".png")
        image = Image.open(image_path).convert("RGB")
        if image.size != (1920, 1080):
            raise SystemExit(f"Incorrect widget render dimensions: {image_path}: {image.size}")
        x = index % columns * tile_width
        y = index // columns * (tile_height + caption)
        montage.paste(image.resize((tile_width, tile_height)), (x, y))
        draw.text((x + 10, y + tile_height + 8), theme["name"], fill="#e7e9ed")
    montage.save("/tmp/sumi-widgets-montage.jpg", quality=92)
    print(f"PASS: {len(themes)} wallpapers × 6 sizes × 4 modes; actual bounds and overlap; cover crop; Spotify independence/empty state; priorities/deadline; normal/battery/reduced/interrupted motion; fullscreen/idle/output gates; gated artwork requests")
    print("Actual QML renders: /tmp/sumi-widgets-<theme-id>.png; /tmp/sumi-widgets-montage.jpg")
    print("Native layer stacking, input regions, DPMS and battery impact require compositor validation.")


if __name__ == "__main__":
    main()
