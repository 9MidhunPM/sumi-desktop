#!/usr/bin/env python3
"""Exercise real marquee frames and lifecycle in a temporary offscreen fixture."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    candidates = (os.environ.get('QML_EXECUTABLE'), '/usr/lib/qt6/bin/qml',
                  '/usr/lib64/qt6/bin/qml', shutil.which('qml6'), shutil.which('qml'))
    qml = next((candidate for candidate in candidates if candidate and os.access(candidate, os.X_OK)), None)
    if qml is None:
        raise SystemExit('Marquee smoke requires Qt 6 qml (or QML_EXECUTABLE)')
    with tempfile.TemporaryDirectory(prefix='sumi-marquee-') as temporary:
        work = Path(temporary)
        (work / 'components').mkdir()
        (work / 'config').mkdir()
        (work / 'runtime').mkdir(mode=0o700)
        shutil.copy2(repo / 'shell/components/MarqueeLabel.qml', work / 'components/MarqueeLabel.qml')
        (work / 'config/qmldir').write_text('singleton Theme 1.0 Theme.qml\n')
        (work / 'config/Theme.qml').write_text('''pragma Singleton
import QtQuick
QtObject {
    property bool effectiveReducedMotion: false
    readonly property color textMain: "white"
    readonly property string font: "Adwaita Sans"
}
''')
        (work / 'smoke.qml').write_text('''import QtQuick
import QtTest
import "components" as C
import "config"
Window {
    id: win
    width: 360; height: 120; visible: true; color: "#17151d"
    C.MarqueeLabel { id: title; x: 20; y: 20; width: 100; text: "A long now-playing title with a visible scrolling tail"; animate: false }
    C.MarqueeLabel { id: loop; x: 20; y: 60; width: 8; text: "AB"; animate: false }
    TestCase {
        name: "SumiMarquee"
        when: win.visible
        function test_lifecycle() {
            verify(title.naturalTextWidth > title.width);
            verify(title.implicitHeight > 0);
            compare(title.Accessible.name, title.text);
            compare(title.scrolling, false);
            compare(title.offset, 0);
            title.animate = true;
            compare(title.scrolling, true);
            wait(300);
            compare(title.offset, 0, "Initial pause lets the title be read");
            wait(700);
            verify(title.offset > 0 && title.offset < 12, "Actual frames begin after the pause");
            const start = title.offset;
            wait(250);
            verify(title.offset - start > 4 && title.offset - start < 11, "Marquee travels about 28px per second");
            title.text = "A different long title resets the animation and initial pause";
            compare(title.offset, 0);
            wait(100);
            compare(title.offset, 0);
            wait(850);
            verify(title.offset > 0);
            Theme.effectiveReducedMotion = true;
            compare(title.scrolling, false);
            compare(title.offset, 0);
            wait(100);
            compare(title.offset, 0);
            Theme.effectiveReducedMotion = false;
            wait(900);
            verify(title.offset > 0);
            title.visible = false;
            compare(title.scrolling, false);
            compare(title.offset, 0);
            title.visible = true;
            compare(title.scrolling, true);
            compare(title.offset, 0);
            title.width = title.naturalTextWidth + 1;
            compare(title.scrolling, false, "Fitting text never animates");
            title.width = 100;
            wait(900);
            verify(title.offset > 0);
            title.animate = false;
            compare(title.scrolling, false);
            compare(title.offset, 0);
            title.text = "Short";
            title.animate = true;
            compare(title.scrolling, false);
            compare(title.offset, 0);

            loop.animate = true;
            const track = findChild(loop, "marqueeTrack");
            verify(!!track);
            compare(track.children.length, 2);
            compare(track.children[0].text, track.children[1].text);
            verify(track.children[1].x > loop.naturalTextWidth);
            wait(900);
            let previous = loop.offset;
            let wrapped = false;
            const deadline = Date.now() + 3000;
            while (!wrapped && Date.now() < deadline) {
                wait(25);
                compare(track.x, -loop.offset);
                if (previous > loop.offset + 5) {
                    verify(previous > loop.naturalTextWidth, "Wrap happens beyond the first title");
                    verify(loop.offset < 3, "Second copy hands off continuously at the origin");
                    wrapped = true;
                }
                previous = loop.offset;
            }
            verify(wrapped, "Two copies complete a continuous animation loop");
            loop.animate = false;
            compare(loop.offset, 0);
            console.info("SUMI_MARQUEE_OK");
            Qt.quit();
        }
    }
}
''')
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', QT_LOGGING_TO_CONSOLE='1', QT_FORCE_STDERR_LOGGING='1',
                           XDG_RUNTIME_DIR=str(work / 'runtime'), DBUS_SESSION_BUS_ADDRESS='unix:path=/nonexistent')
        result = subprocess.run([qml, str(work / 'smoke.qml')], env=environment, capture_output=True, text=True, timeout=15)
        output = result.stdout + result.stderr
        if result.returncode or 'SUMI_MARQUEE_OK' not in output or any(value in output for value in ('FAIL!', 'TypeError:', 'ReferenceError:', 'Unable to', 'not available', 'Error:')):
            raise SystemExit(f'Marquee QML smoke failed, exit {result.returncode}:\n{output}')
        print('PASS marquee: initial pause, real frames/speed, continuous wrap, text reset, reduced/hidden/inactive/fit stops')


if __name__ == '__main__':
    main()
