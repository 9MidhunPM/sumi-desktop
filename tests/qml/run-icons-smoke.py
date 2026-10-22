#!/usr/bin/env python3
"""Render local icons and exercise icon buttons without touching the desktop.

Copies the real components/assets into a temporary fixture with a passive theme.
Qt's software renderer provides pixel evidence at normal, fractional, and HiDPI
scales, while real key events check button compatibility. All fixtures and
screenshots are removed on success or failure; native compositor QA is separate.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from PIL import Image, ImageChops


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    candidates = (os.environ.get('QML_EXECUTABLE'), '/usr/lib/qt6/bin/qml',
                  '/usr/lib64/qt6/bin/qml', shutil.which('qml6'), shutil.which('qml'))
    qml = next((candidate for candidate in candidates if candidate and os.access(candidate, os.X_OK)), None)
    if qml is None:
        raise SystemExit('Icon smoke requires the Qt 6 qml executable (or QML_EXECUTABLE)')
    with tempfile.TemporaryDirectory(prefix='sumi-icons-') as temporary:
        work = Path(temporary)
        (work / 'components').mkdir()
        (work / 'config').mkdir()
        (work / 'runtime').mkdir(mode=0o700)
        pattern = Image.new('RGBA', (24, 24), (0, 0, 0, 255))
        for y in range(24):
            for x in range(12, 24):
                pattern.putpixel((x, y), (255, 255, 255, 255))
        for y in range(4):
            for x in range(4):
                pattern.putpixel((x, y), (0, 0, 0, 0))
        for y in range(18, 24):
            for x in range(12, 24):
                pattern.putpixel((x, y), (255, 255, 255, 128))
        pattern.save(work / 'app-pattern.png')
        for name in ('Icon.qml', 'ActionButton.qml', 'Label.qml'):
            shutil.copy2(repo / 'shell/components' / name, work / 'components' / name)
        shutil.copytree(repo / 'shell/assets', work / 'assets')
        (work / 'config/qmldir').write_text('singleton Theme 1.0 Theme.qml\n')
        (work / 'config/Theme.qml').write_text('''pragma Singleton
        import QtQuick
        QtObject {
            readonly property color textMain: "#f3e9df"
            readonly property color desktopBackground: "#17151d"
            readonly property color accentBlue: "#b8b5d9"
            readonly property color bgPlaying: "#49333e"
            readonly property color bgPanelStrong: "#f51c1b23"
            readonly property color borderSoft: "#44c9aab8"
            readonly property bool effectiveReducedMotion: true
            readonly property int motionControl: 0
            readonly property string font: "Adwaita Sans"
            readonly property int fontSize: 13
        }
        ''')
        names = [
            'arch', 'arrow-right', 'battery', 'battery-charging', 'bell', 'bell-off',
            'bluetooth', 'bluetooth-off', 'calendar', 'chatgpt', 'chevron-down', 'chevron-up',
            'circle-help', 'code', 'grid', 'more-horizontal', 'music', 'pause', 'play',
            'settings', 'sparkles', 'terminal', 'volume', 'volume-x', 'wifi', 'wifi-off',
            'apps', 'assistant', 'codex', 'unknown',
        ]
        source = '''import QtQuick
        import QtTest
        import "components" as C
        Window {
            id: win
            width: 720; height: 420; visible: true; color: "#101015"
            property int presses: 0
            property bool saved: false
            Repeater {
                id: icons
                model: ICON_NAMES
                delegate: Item {
                    required property string modelData
                    required property int index
                    property alias icon: glyph
                    x: (index % 8) * 90; y: Math.floor(index / 8) * 72
                    width: 90; height: 72
                    C.Icon { id: glyph; x: 33; y: 10; name: parent.modelData; size: 24; color: "#e875a5" }
                    Text { y: 40; width: 90; text: parent.modelData; font.pixelSize: 9; color: "white"; horizontalAlignment: Text.AlignHCenter }
                }
            }
            C.ActionButton { id: iconOnly; x: 20; y: 310; width: 28; height: 36; iconName: "wifi"; iconColor: "#64dab5"; tooltip: "Network"; onClicked: win.presses++ }
            C.ActionButton { id: textOnly; x: 70; y: 310; text: "Text button"; tooltip: "Text action"; onClicked: win.presses++ }
            C.ActionButton { id: combined; x: 220; y: 310; iconName: "battery"; text: "80%"; tooltip: "Control center"; onClicked: win.presses++ }
            C.Icon { id: changing; x: 340; y: 316; name: "wifi"; color: "red"; size: 24 }
            C.Icon { id: empty; x: 390; y: 316; name: ""; size: 24 }
            C.Icon { id: detailed; x: 450; y: 316; source: Qt.resolvedUrl("app-pattern.png"); size: 24; color: "#64dab5" }
            C.Icon { id: translucent; x: 490; y: 316; source: Qt.resolvedUrl("app-pattern.png"); size: 24; color: Qt.rgba(100 / 255, 218 / 255, 181 / 255, 0.5); preserveDetail: true }
            TestCase {
                name: "SumiIcons"
                when: win.visible
                function test_icons() {
                    for (let index = 0; index < icons.count; index++)
                        tryCompare(icons.itemAt(index).icon, "ready", true, 3000,
                                   "SVG did not load: " + icons.itemAt(index).modelData);
                    wait(100);
                    compare(iconOnly.Accessible.name, "Network");
                    compare(textOnly.Accessible.name, "Text action");
                    compare(combined.Accessible.name, "Control center");
                    iconOnly.forceActiveFocus(Qt.TabFocusReason);
                    keyClick(Qt.Key_Return);
                    keyClick(Qt.Key_Space);
                    keyClick(Qt.Key_Tab);
                    verify(textOnly.activeFocus, "Tab did not preserve button focus order");
                    keyClick(Qt.Key_Return);
                    keyClick(Qt.Key_Tab);
                    verify(combined.activeFocus, "Icon and text button lost Tab focus");
                    keyClick(Qt.Key_Space);
                    compare(win.presses, 4);
                    changing.name = "bell";
                    changing.color = "#64dab5";
                    changing.size = 32;
                    tryCompare(detailed, "ready", true, 3000);
                    tryCompare(translucent, "ready", true, 3000);
                    detailed.preserveDetail = true;
                    wait(150);
                    verify(changing.ready, "Changing icon did not load");
                    compare(changing.width, 32);
                    win.contentItem.grabToImage(function(image) { win.saved = image.saveToFile(OUTPUT_PATH); });
                    tryCompare(win, "saved", true, 3000);
                    console.info("SUMI_ICONS_OK");
                    Qt.quit();
                }
            }
        }
        '''.replace('ICON_NAMES', json.dumps(names)).replace('OUTPUT_PATH', json.dumps(str(work / 'preview.png')))
        (work / 'smoke.qml').write_text(source)
        for scale in ('1', '1.5', '2'):
            environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', QT_SCALE_FACTOR=scale,
                               XDG_RUNTIME_DIR=str(work / 'runtime'), DBUS_SESSION_BUS_ADDRESS='unix:path=/nonexistent')
            (work / 'preview.png').unlink(missing_ok=True)
            result = subprocess.run([qml, str(work / 'smoke.qml')], env=environment, capture_output=True, text=True, timeout=12)
            output = result.stdout + result.stderr
            if result.returncode or not (work / 'preview.png').exists() or any(value in output for value in ('FAIL!', 'TypeError:', 'ReferenceError:', 'Unable to', 'not available', 'Error:')):
                raise SystemExit(f'Icon QML smoke failed at scale {scale}, exit {result.returncode}:\n{output}')
            with Image.open(work / 'preview.png') as rendered:
                image = rendered.convert('RGB')
                rgba = rendered.convert('RGBA')
            ratio = image.width / 720
            def crop(x, y, width, height):
                # Round half pixels consistently across columns at 150% scale.
                return image.crop(tuple(int(value * ratio + 0.5) for value in (x, y, x + width, y + height)))
            def matches(tile, color, tolerance=12):
                return sum(
                    all(abs(pixel[channel] - color[channel]) < tolerance for channel in range(3))
                    for y in range(tile.height)
                    for pixel in (tile.getpixel((x, y)) for x in range(tile.width))
                )
            for index, name in enumerate(names):
                pixels = matches(crop((index % 8) * 90 + 33, (index // 8) * 72 + 10, 24, 24), (232, 117, 165))
                assert pixels >= 3, f'{name} is blank or incorrectly tinted at scale {scale}: {pixels} pixels'
            def icon_tile(name):
                index = names.index(name)
                return crop((index % 8) * 90 + 33, (index // 8) * 72 + 10, 24, 24)
            assert ImageChops.difference(icon_tile('codex'), icon_tile('chatgpt')).getbbox() is None, 'Codex must render the ChatGPT mark'
            assert ImageChops.difference(icon_tile('chatgpt'), icon_tile('unknown')).getbbox() is not None, 'ChatGPT mark rendered the fallback icon'
            compact = crop(20, 310, 28, 36)
            points = [(x, y) for y in range(compact.height) for x in range(compact.width)
                      if compact.getpixel((x, y))[1] > compact.getpixel((x, y))[0] * 1.4 and compact.getpixel((x, y))[1] > compact.getpixel((x, y))[2] * 1.1]
            assert points, 'Compact icon is blank'
            center = (min(x for x, _ in points) + max(x for x, _ in points)) / 2
            assert abs(center - compact.width / 2) <= 2 * ratio, ('Icon not centered', center)
            assert matches(crop(340, 316, 32, 32), (100, 218, 181)) >= 3, 'Tint/size update failed'
            assert matches(crop(353, 318, 6, 5), (100, 218, 181)) >= 1, 'Source change retained the old Wi-Fi shape'
            assert matches(crop(85, 316, 100, 24), (243, 233, 223)) >= 8, 'Text-only label is not visible'
            # A 20px icon at fractional scale can have no fully opaque pixels;
            # allow its antialiasing while still excluding the dark background.
            assert matches(crop(230, 316, 26, 24), (243, 233, 223), 45) >= 3, 'Icon and text button lost its icon'
            assert matches(crop(259, 316, 28, 24), (243, 233, 223), 35) >= 5, 'Icon and text button lost its label'
            assert all(low == high for low, high in crop(390, 316, 24, 24).getextrema()), 'Empty icon was painted'
            dark = crop(453, 324, 4, 4)
            light = crop(467, 324, 4, 4)
            assert matches(dark, (60, 131, 109), 5) >= 3, f'App logo lost its dark internal detail: {dark.getextrema()}'
            assert matches(light, (100, 218, 181), 5) >= 3, f'App logo lost its light internal detail: {light.getextrema()}'
            def alpha_at(x, y):
                return rgba.getpixel((int(x * ratio + 0.5), int(y * ratio + 0.5)))[3]
            assert alpha_at(451, 317) <= 2, 'Detail tint filled transparent source pixels'
            assert abs(alpha_at(495, 328) - 128) <= 3, 'Detail tint ignored theme alpha'
            assert abs(alpha_at(508, 337) - 64) <= 3, 'Detail tint did not multiply source and theme alpha'
            print('PASS scale', scale, ':', len(names), 'SVGs/aliases/fallback; compact centering; keyboard/accessibility; live updates; app detail and alpha')


if __name__ == "__main__":
    main()
