"""Read-only backlight observer tests; every device is a temporary fixture."""
import io
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from sumi.actions import brightness_device, brightness_snapshot, watch_brightness


class BrightnessWatchTests(unittest.TestCase):
    def test_selected_device_must_be_a_backlight_and_a_single_safe_name(self):
        for value in ("asus::kbd_backlight,leds,0,0%,3", "../bad,backlight,0,0%,3", "a/b,backlight,0,0%,3", "a,backlight,0,0%,3\nb,backlight,0,0%,3"):
            with self.subTest(value=value), patch("sumi.actions.run", return_value=subprocess.CompletedProcess([], 0, value)):
                with self.assertRaises(RuntimeError):
                    brightness_device()
        with patch("sumi.actions.run", return_value=subprocess.CompletedProcess([], 0, "intel_backlight,backlight,400,40%,1000")):
            self.assertEqual(brightness_device(), Path("/sys/class/backlight/intel_backlight"))

    def test_snapshot_uses_actual_zero_and_rejects_invalid_hardware_values(self):
        with tempfile.TemporaryDirectory() as directory:
            device = Path(directory)
            (device / "brightness").write_text("70\n")
            (device / "max_brightness").write_text("100\n")
            self.assertEqual(brightness_snapshot(device)["percent"], 70)
            (device / "actual_brightness").write_text("0\n")
            self.assertEqual(brightness_snapshot(device)["percent"], 0)
            for actual, maximum in (("-1", "100"), ("101", "100"), ("0", "0")):
                (device / "actual_brightness").write_text(actual)
                (device / "max_brightness").write_text(maximum)
                with self.assertRaises(RuntimeError):
                    brightness_snapshot(device)

    def test_watcher_blocks_on_kernel_events_dedupes_and_closes_descriptors(self):
        with tempfile.TemporaryDirectory() as directory:
            device = Path(directory)
            (device / "brightness").write_text("40")
            (device / "actual_brightness").write_text("40")
            (device / "max_brightness").write_text("100")
            descriptors = []

            class FixturePoll:
                calls = 0

                def register(self, descriptor, flags):
                    descriptors.append(descriptor)
                    self.flags = flags

                def poll(self, timeout):
                    self.calls += 1
                    if self.calls == 4:
                        raise InterruptedError("fixture stopped")
                    (device / "actual_brightness").write_text("50" if self.calls < 3 else "60")
                    return [(descriptors[0], select.POLLPRI)]

            poller = FixturePoll()
            with patch("sumi.actions.brightness_device", return_value=device) as discover, patch("sumi.actions.select.poll", return_value=poller), patch("sys.stdout", new_callable=io.StringIO) as output:
                with self.assertRaises(InterruptedError):
                    watch_brightness()
            self.assertEqual([json.loads(line)["percent"] for line in output.getvalue().splitlines()], [40, 50, 60])
            discover.assert_called_once_with()
            self.assertEqual(poller.flags, select.POLLPRI | select.POLLERR)
            for descriptor in descriptors:
                with self.assertRaises(OSError):
                    os.fstat(descriptor)


if __name__ == "__main__":
    unittest.main()
