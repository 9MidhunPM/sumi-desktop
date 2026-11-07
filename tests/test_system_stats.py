"""Read-only system metric fixtures, byte accounting and observer cadence."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from collections import namedtuple

from sumi.system_stats import Sampler, cpu_percent, parse_cpu, parse_memory, watch

Disk = namedtuple("Disk", "total used free")


class SystemStatsTests(unittest.TestCase):
    def test_cpu_aggregate_excludes_guest_double_counting_and_iowait(self):
        before = parse_cpu("cpu  100 20 30 400 50 10 20 0 90 10\ncpu0 1 1 1 1\n")
        after = parse_cpu("cpu  120 20 40 440 70 10 30 0 9000 1000\n")
        self.assertEqual(after.total - before.total, 100)
        self.assertEqual(cpu_percent(before, after), 40)
        self.assertEqual(cpu_percent(before, before), None)
        self.assertIsNone(cpu_percent(None, after))

    def test_cpu_counter_resets_invalidate_one_interval(self):
        before = parse_cpu("cpu 100 20 30 400 50 10 20 0")
        reset = parse_cpu("cpu 10 20 30 600 50 10 20 0")
        self.assertIsNone(cpu_percent(before, reset))
        recovered = parse_cpu("cpu 20 20 30 610 50 10 20 0")
        self.assertEqual(cpu_percent(reset, recovered), 50)
        for fixture in ("cpu0 1 2 3 4", "cpu 1 2 3", "cpu 1 two 3 4", "cpu 1 2 3 -4"):
            with self.subTest(fixture=fixture), self.assertRaises(ValueError):
                parse_cpu(fixture)

    def test_memory_uses_memavailable_and_converts_kib_to_bytes(self):
        used, total = parse_memory("MemTotal: 1000 kB\nMemFree: 5 kB\nCached: 300 kB\nMemAvailable: 400 kB\n")
        self.assertEqual((used, total), (600 * 1024, 1000 * 1024))
        for fixture in ("MemTotal: 1000 kB\nMemFree: 4 kB", "MemTotal: 0 kB\nMemAvailable: 0 kB", "MemTotal: 2 kB\nMemAvailable: 3 kB", "MemTotal: 2 MB\nMemAvailable: 1 kB"):
            with self.subTest(fixture=fixture), self.assertRaises((KeyError, ValueError)):
                parse_memory(fixture)

    def test_sampler_partial_failures_clear_missing_values_and_recover_cpu_baseline(self):
        with tempfile.TemporaryDirectory() as temporary:
            proc = Path(temporary)
            (proc / "stat").write_text("cpu 100 0 0 100 0 0 0 0")
            (proc / "meminfo").write_text("MemTotal: 1000 kB\nMemAvailable: 250 kB\n")
            sampler = Sampler(proc)
            sampler.prime()
            (proc / "stat").write_text("cpu 125 0 0 175 0 0 0 0")
            with patch("sumi.system_stats.shutil.disk_usage", return_value=Disk(9000, 6000, 2500)) as disk:
                sample = sampler.sample()
            disk.assert_called_once_with("/")
            self.assertEqual(sample["cpuPercent"], 25)
            self.assertEqual(sample["memoryUsed"], 750 * 1024)
            self.assertEqual((sample["storageUsed"], sample["storageTotal"], sample["storageFree"]), (6000, 9000, 2500))
            self.assertEqual(sample["error"], "")
            (proc / "stat").unlink()
            (proc / "meminfo").write_text("invalid")
            with patch("sumi.system_stats.shutil.disk_usage", side_effect=OSError("not mounted")):
                failed = sampler.sample()
            self.assertFalse(failed["cpuAvailable"] or failed["memoryAvailable"] or failed["storageAvailable"])
            self.assertIsNone(failed["cpuPercent"])
            self.assertIsNone(failed["memoryUsed"])
            self.assertIsNone(failed["storageUsed"])
            self.assertIn("unavailable", failed["error"])
            (proc / "stat").write_text("cpu 150 0 0 200")
            with patch("sumi.system_stats.shutil.disk_usage", return_value=Disk(9000, 6000, 3000)):
                recovered = sampler.sample()
            self.assertFalse(recovered["cpuAvailable"])
            self.assertTrue(recovered["storageAvailable"])

    def test_watch_has_a_short_initial_baseline_then_two_second_cadence(self):
        fixture = {"cpuPercent": 17.5, "cpuAvailable": True}
        with patch("sumi.system_stats.Sampler") as sampler, patch("sumi.system_stats.time.sleep", side_effect=[None, None, KeyboardInterrupt]) as sleep, patch("sys.stdout", new_callable=io.StringIO) as output:
            sampler.return_value.sample.return_value = fixture
            watch()
            self.assertEqual([json.loads(line) for line in output.getvalue().splitlines()], [fixture, fixture])
            sampler.return_value.prime.assert_called_once_with()
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [.2, 2, 2])


if __name__ == "__main__":
    unittest.main()
