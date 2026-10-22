"""Exercise the real QML clock formatter without connecting to the desktop."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("qs"), "Quickshell is required for the clock QML test")
class ClockTests(unittest.TestCase):
    def test_twelve_hour_boundaries_and_public_properties(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="sumi-clock-") as directory:
            work = Path(directory)
            config = work / "config"
            services = config / "services"
            services.mkdir(parents=True)
            shutil.copyfile(repo / "shell/services/Clock.qml", services / "Clock.qml")
            (services / "qmldir").write_text("singleton Clock Clock.qml\n")
            (config / "shell.qml").write_text('''
import QtQuick
import Quickshell
import "services" as S

ShellRoot {
    Timer {
      interval: 10
      running: true
      onTriggered: {
        const cases = [
            [0, 0, "12:00", "AM"], [0, 5, "12:05", "AM"],
            [1, 2, "1:02", "AM"], [11, 59, "11:59", "AM"],
            [12, 0, "12:00", "PM"], [12, 5, "12:05", "PM"],
            [13, 9, "1:09", "PM"], [23, 59, "11:59", "PM"]
        ];
        for (const sample of cases) {
            const parts = S.Clock.formatTime(new Date(2026, 0, 15, sample[0], sample[1]));
            if (parts.time !== sample[2] || parts.period !== sample[3]
                || parts.hour + ":" + parts.minute !== sample[2]
                || parts.accessibleTime !== sample[2] + " " + sample[3]) {
                console.error("SUMI_CLOCK_FAILED", JSON.stringify(sample), JSON.stringify(parts));
                Qt.exit(1);
                return;
            }
        }
        const current = S.Clock.formatTime(S.Clock.date);
        if (S.Clock.time !== current.time || S.Clock.period !== current.period
            || S.Clock.hour !== current.hour || S.Clock.minute !== current.minute
            || S.Clock.accessibleTime !== current.accessibleTime
            || S.Clock.dateShort !== S.Clock.dateLabel || !S.Clock.dateShort.length) {
            console.error("SUMI_CLOCK_FAILED", "Public clock properties disagree");
            Qt.exit(1);
            return;
        }
        console.info("SUMI_CLOCK_OK");
        Qt.quit();
      }
    }
}
''')
            runtime = work / "runtime"
            runtime.mkdir(mode=0o700)
            environment = dict(os.environ, SUMI_PREVIEW="1", QT_QPA_PLATFORM="offscreen",
                               XDG_RUNTIME_DIR=str(runtime), HOME=str(work),
                               XDG_CONFIG_HOME=str(work / "xdg-config"), XDG_CACHE_HOME=str(work / "cache"))
            result = subprocess.run(["qs", "-p", str(config), "-n"], env=environment,
                                    text=True, capture_output=True, timeout=10)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("SUMI_CLOCK_OK", output)
            self.assertNotIn("SUMI_CLOCK_FAILED", output)


if __name__ == "__main__":
    unittest.main()
