"""Classic daemon startup never inherits the controller's response pipes."""
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from sumi import profiles


class ClassicEwwStartupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.state = self.home / "state"
        environment = patch.dict(os.environ, {"SUMI_DRY_RUN": "0", "SUMI_STATE_DIR": str(self.state)})
        environment.start()
        self.addCleanup(environment.stop)

    def test_classic_waits_for_daemon_and_widget_without_inheritable_capture_pipes(self):
        config = self.home / ".config/eww/eww.yuck"
        config.parent.mkdir(parents=True)
        config.write_text("(defwindow clock_window (label :text `Clock`))")
        commands, pings, windows = [], iter(["", "pong\n"]), iter(["other: clock_window\n", "clock_window: clock_window\n"])

        def execute(command, **options):
            commands.append(command)
            if command[0] != "eww":
                return subprocess.CompletedProcess(command, 0, "", "")
            self.assertEqual(command[1:4], ["--force-wayland", "--config", str(config.parent)])
            if "daemon" in command:
                # Simulate the native double-fork keeping a captured pipe open.
                if options.get("capture_output") or options.get("stdout") == subprocess.PIPE:
                    raise subprocess.TimeoutExpired(command, options["timeout"])
                self.assertTrue(stat.S_ISREG(os.fstat(options["stdout"].fileno()).st_mode))
                self.assertEqual(options["stderr"], subprocess.STDOUT)
                self.assertEqual(options["stdin"], subprocess.DEVNULL)
                self.assertTrue(options["start_new_session"])
                options["stdout"].write(b"daemon diagnostics\n")
                return subprocess.CompletedProcess(command, 0)
            if command[-1] == "ping":
                response = next(pings)
                return subprocess.CompletedProcess(command, 0 if response else 1, response, "")
            if "open" in command:
                self.assertIn("--no-daemonize", command)
                self.assertEqual(commands[-2][-1], "ping")
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[-1] == "active-windows":
                return subprocess.CompletedProcess(command, 0, next(windows), "")
            self.fail(f"Unexpected Eww command: {command}")

        with patch.object(profiles.subprocess, "run", side_effect=execute), \
             patch.object(profiles, "_service_restore"), patch.object(profiles, "_wait_classic_ready") as ready, \
             patch.object(profiles.time, "sleep"):
            profiles._start_classic(self.home, {})
        ready.assert_called_once_with(self.home, dry_run=False)
        self.assertEqual(sum(command[-1] == "active-windows" for command in commands), 2)
        log = self.state / "classic-eww.log"
        self.assertEqual(log.read_text(), "daemon diagnostics\n")
        self.assertEqual(stat.S_IMODE(log.stat().st_mode), 0o600)

    def test_daemon_failure_does_not_attempt_open(self):
        with patch.object(profiles.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)), \
             patch.object(profiles, "_run") as run:
            with self.assertRaisesRegex(profiles.ProfileError, "daemon startup failed.*classic-eww.log"):
                profiles._start_classic_eww(self.home)
        run.assert_not_called()

    def test_unresponsive_daemon_has_bounded_readiness_and_never_opens_widget(self):
        with patch.object(profiles.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)), \
             patch.object(profiles, "_run", return_value=subprocess.CompletedProcess([], 1, "", "not ready")) as run, \
             patch.object(profiles.time, "monotonic", side_effect=[0, 0, 16, 16]), \
             patch.object(profiles.time, "sleep"):
            with self.assertRaisesRegex(profiles.ProfileError, "did not answer ping"):
                profiles._start_classic_eww(self.home)
        self.assertEqual(len(run.call_args_list), 1)
        self.assertEqual(run.call_args.args[0][-1], "ping")
        self.assertLessEqual(run.call_args.kwargs["timeout"], 2)

    def test_open_success_does_not_count_as_visible_widget(self):
        def response(command, **kwargs):
            text = "pong\n" if command[-1] == "ping" else "other: clock_window\n"
            return subprocess.CompletedProcess(command, 0, text, "")
        with patch.object(profiles.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)), \
             patch.object(profiles, "_run", side_effect=response), \
             patch.object(profiles.time, "monotonic", side_effect=[0, 0, 1, 2, 16, 16]), \
             patch.object(profiles.time, "sleep"):
            with self.assertRaisesRegex(profiles.ProfileError, "did not show clock_window"):
                profiles._start_classic_eww(self.home)

    def test_dry_run_never_spawns_daemon_or_writes_log(self):
        with patch.object(profiles.subprocess, "run") as run:
            profiles._start_classic_eww(self.home, dry_run=True)
        run.assert_not_called()
        self.assertFalse(self.state.exists())


if __name__ == "__main__":
    unittest.main()
