"""Session boundaries are tested with fresh paths and mocked user services."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from sumi import session


class SessionArtifactsTests(unittest.TestCase):
    def artifacts(self, base):
        return session.build_artifacts(base / "data/sumi/runtime", base / "settings",
                                       base / "data/sumi", base / "state/sumi", base / "bin", home=base)

    def test_rendering_writes_nothing_and_supports_spaces(self):
        with tempfile.TemporaryDirectory(prefix="sumi session ") as temporary:
            base = Path(temporary) / "unused home"
            files = self.artifacts(base)
            self.assertFalse(base.exists())
            self.assertIn(base / "settings/hypr/hyprland.lua", files)
            self.assertIn(base / "settings/systemd/user/sumi-session.target", files)
            lua = files[base / "settings/hypr/hyprland.lua"][0].decode()
            declaration = next(line for line in lua.splitlines() if line.startswith("local controller = "))
            command = json.loads(declaration.split(" = ", 1)[1])
            self.assertEqual(shlex.split(command), [str(base / "data/sumi/runtime/bin/desktopctl")])
            idle = files[base / "settings/hypr/hypridle.conf"][0].decode()
            lock = next(line.split(" = ", 1)[1] for line in idle.splitlines() if "lock_cmd = " in line)
            self.assertEqual(shlex.split(lock), ["systemctl", "--user", "start", "sumi-lock.service"])

    def test_shell_metacharacters_are_literals(self):
        base = Path("/tmp/Sumi's $HOME %n; $(false)")
        files = self.artifacts(base)
        lua = files[base / "settings/hypr/hyprland.lua"][0].decode()
        command = json.loads(next(line.split(" = ", 1)[1] for line in lua.splitlines() if line.startswith("local controller = ")))
        self.assertEqual(shlex.split(command), [str(base / "data/sumi/runtime/bin/desktopctl")])
        unit = files[base / "settings/systemd/user/sumi-shell.service"][0].decode()
        self.assertIn("$$HOME %%n; $$(false)", unit)
        self.assertIn('Environment="SUMI_HOME=/tmp/Sumi\'s $HOME %%n; $(false)"', unit)

    def test_paths_with_control_characters_are_rejected_before_writing(self):
        with self.assertRaisesRegex(ValueError, "control characters"):
            self.artifacts(Path("/tmp/unsafe\npath"))

    def test_relative_paths_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "absolute"):
            self.artifacts(Path("relative"))

    def test_session_has_no_boot_enablement_and_every_daemon_is_scoped(self):
        files = self.artifacts(Path("/tmp/home"))
        for path, (content, mode) in files.items():
            if path.suffix == ".service":
                self.assertIn("PartOf=sumi-session.target", content.decode(), str(path))
                self.assertNotIn("WantedBy=graphical-session.target", content.decode())
            self.assertEqual(mode, 0o644)

    def test_lua_uses_automatic_monitors_and_no_machine_identifiers(self):
        files = self.artifacts(Path("/tmp/home"))
        lua = files[Path("/tmp/home/settings/hypr/hyprland.lua")][0].decode()
        self.assertIn('mode = "preferred", position = "auto", scale = "auto"', lua)
        self.assertIn("for workspace = 1, 10", lua)
        self.assertIn('"SUPER + SHIFT + " .. key', lua)
        self.assertNotIn("eDP-1", lua)
        self.assertNotIn("HDMI-A-1", lua)

    def test_lock_policy_waits_for_compositor_confirmation_and_respects_inhibitors(self):
        files = self.artifacts(Path("/tmp/home"))
        idle = files[Path("/tmp/home/settings/hypr/hypridle.conf")][0].decode()
        self.assertIn("inhibit_sleep = 3", idle)
        self.assertNotIn("ignore_dbus_inhibit = true", idle)
        self.assertNotIn("brightnessctl", idle)

    def test_fallback_lock_palette_is_replaced_when_a_theme_is_selected(self):
        from sumi import themes
        base = Path("/tmp/home")
        lock = self.artifacts(base)[base / "settings/hypr/hyprlock.conf"][0].decode()
        theme = themes.get_theme("sumi-ember", home=base, state_dir=base / "state", data_dir=base / "data")
        updated, variables = themes._hyprlock(lock, theme, base / "settings/sumi/generated/hyprlock.conf")
        self.assertNotIn("$sumi_wallpaper = screenshot", updated)
        self.assertIn("source = /tmp/home/settings/sumi/generated/hyprlock.conf", updated)
        self.assertIn(theme["wallpaper"], variables)


class SessionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.environment = {
            "HOME": "/tmp/sumi user", "PATH": "/usr/bin", "WAYLAND_DISPLAY": "wayland-1",
            "HYPRLAND_INSTANCE_SIGNATURE": "sumi-test", "XDG_RUNTIME_DIR": "/tmp/sumi-runtime",
            "API_TOKEN": "do-not-import-this",
        }

    def test_dry_run_invokes_no_programs_or_clipboard_storage(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(session, "_run") as run:
            result = session.start(dry_run=True)
        run.assert_not_called()
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["started"])

    def test_start_requires_a_compositor_environment(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(session, "_run") as run:
            with self.assertRaisesRegex(RuntimeError, "Hyprland session"):
                session.start()
        run.assert_not_called()

    def test_environment_import_precedes_portals_and_shell(self):
        with patch.dict(os.environ, self.environment, clear=True), patch.object(session, "_run") as run, \
             patch("sumi.actions.restore_clipboard_watchers") as clipboard:
            result = session.start(state_dir=Path("/tmp/state"))
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0][:3], ["systemctl", "--user", "import-environment"])
        self.assertEqual(commands[1][:2], ["dbus-update-activation-environment", "--systemd"])
        self.assertNotIn("API_TOKEN", commands[0])
        self.assertEqual(commands[-1], ["systemctl", "--user", "start", "sumi-session.target"])
        self.assertTrue(result["started"])
        clipboard.assert_called_once_with(state_dir=Path("/tmp/state"))

    def test_optional_audio_failure_does_not_prevent_desktop_start(self):
        def command(argv, **kwargs):
            if "pipewire.socket" in argv:
                raise RuntimeError("Audio unavailable")
            return Mock(returncode=0, stdout="")
        with patch.dict(os.environ, self.environment, clear=True), patch.object(session, "_run", side_effect=command) as run, \
             patch("sumi.actions.restore_clipboard_watchers"), patch.object(session, "restore_wallpaper", return_value={"applied": False}):
            result = session.start()
        self.assertTrue(result["started"])
        self.assertIn("Audio unavailable", result["warnings"])
        self.assertIn(["systemctl", "--user", "start", "sumi-session.target"], [call.args[0] for call in run.call_args_list])

    def test_stop_never_terminates_other_desktops(self):
        with patch.object(session, "_run") as run:
            session.stop()
        run.assert_called_once_with(["systemctl", "--user", "stop", "sumi-session.target"])

    def test_suspend_refuses_without_lock_notification_inhibitor(self):
        with patch.object(session, "_run", return_value=Mock(returncode=3, stdout="inactive\n")) as run:
            with self.assertRaisesRegex(RuntimeError, "idle service"):
                session.suspend()
        self.assertEqual(run.call_count, 1)

    def test_suspend_requests_lock_before_sleep(self):
        with patch.object(session, "_run", return_value=Mock(returncode=0, stdout="active\n")) as run:
            session.suspend()
        self.assertEqual([call.args[0] for call in run.call_args_list], [
            ["systemctl", "--user", "is-active", "sumi-idle.service"],
            ["systemctl", "--user", "start", "sumi-lock.service"], ["systemctl", "suspend"],
        ])

    def test_watch_stops_session_when_compositor_socket_closes(self):
        connection = Mock()
        connection.recv.side_effect = [b"workspace>>1\n", b""]
        context = Mock()
        context.__enter__ = Mock(return_value=connection)
        context.__exit__ = Mock(return_value=False)
        with patch.dict(os.environ, self.environment, clear=True), patch.object(session.socket, "socket", return_value=context), \
             patch.object(session, "_run") as run:
            session.watch()
        connection.connect.assert_called_once_with("/tmp/sumi-runtime/hypr/sumi-test/.socket2.sock")
        run.assert_called_once_with(["systemctl", "--user", "--no-block", "stop", "sumi-session.target"], check=False)


class LoginWallpaperTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sumi wallpaper ")
        self.addCleanup(self.temporary.cleanup)
        self.state = Path(self.temporary.name)
        self.wallpaper = self.state / "warm image.png"
        self.wallpaper.write_bytes(b"synthetic image")
        self.theme = self.state / "theme.json"
        self.theme.write_text(json.dumps({"wallpaper": str(self.wallpaper), "sourceSize": [1920, 1080]}))

    def test_readiness_retry_applies_image_then_scene_without_changing_theme(self):
        original = self.theme.read_bytes()
        def apply(argv, **kwargs):
            self.assertFalse((self.state / "scene.json").exists())
            self.assertEqual(argv, ["awww", "img", "--transition-type", "none", str(self.wallpaper)])
        with patch.object(session.subprocess, "run", side_effect=[Mock(returncode=1), Mock(returncode=0)]) as query, \
             patch.object(session, "_run", side_effect=apply), patch.object(session.time, "sleep"):
            result = session.restore_wallpaper(state_dir=self.state)
        self.assertEqual(query.call_count, 2)
        self.assertTrue(result["applied"])
        self.assertEqual(self.theme.read_bytes(), original)
        self.assertEqual(json.loads((self.state / "scene.json").read_text())["wallpaper"], str(self.wallpaper))

    def test_failed_wallpaper_does_not_publish_widget_scene(self):
        with patch.object(session.subprocess, "run", return_value=Mock(returncode=0)), \
             patch.object(session, "_run", side_effect=RuntimeError("Image rejected")):
            with self.assertRaisesRegex(RuntimeError, "Image rejected"):
                session.restore_wallpaper(state_dir=self.state)
        self.assertFalse((self.state / "scene.json").exists())

    def test_readiness_has_a_retry_limit(self):
        with patch.object(session.subprocess, "run", return_value=Mock(returncode=1)) as query, \
             patch.object(session, "_run") as apply, patch.object(session.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "did not become ready"):
                session.restore_wallpaper(state_dir=self.state)
        self.assertEqual(query.call_count, 20)
        apply.assert_not_called()


if __name__ == "__main__":
    unittest.main()
