"""Exercise the recovery seams without touching the real session or home."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import signal
import sys
import tempfile
import types
import subprocess
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from sumi import profiles


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.snapshot = self.base / "backup"

    def write(self, relative, content, mode=0o600):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(mode)
        return path

    def test_restore_bytes_permissions_symlink_and_initially_missing(self):
        path = self.write(".config/sample.conf", "original\n", 0o640)
        link = self.home / ".config/link"
        link.symlink_to("sample.conf")
        profiles.capture_snapshot(self.home, self.snapshot, paths=(".config/sample.conf", ".config/link", ".config/new.conf"))
        path.write_text("changed")
        path.chmod(0o600)
        link.unlink()
        link.write_text("wrong type")
        self.write(".config/new.conf", "introduced by theme")
        profiles.restore_snapshot(self.snapshot, self.home)
        self.assertEqual(path.read_text(), "original\n")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), "sample.conf")
        self.assertFalse((self.home / ".config/new.conf").exists())
        self.assertEqual(stat.S_IMODE(self.snapshot.stat().st_mode), 0o700)

    def test_checksum_error_is_detected_before_home_is_touched(self):
        first = self.write("first", "first original")
        second = self.write("second", "second original")
        profiles.capture_snapshot(self.home, self.snapshot, paths=("first", "second"))
        first.write_text("current")
        profiles.snapshot_object(self.snapshot, "second").write_text("corrupt backup")
        with self.assertRaisesRegex(profiles.ProfileError, "mismatch"):
            profiles.restore_snapshot(self.snapshot, self.home)
        self.assertEqual(first.read_text(), "current")
        self.assertEqual(second.read_text(), "second original")

    def test_external_qml_targets_are_archived_without_dereferencing_live_link(self):
        external = self.base / "integration"
        external.mkdir()
        (external / "Voice.qml").write_text("original integration")
        quickshell = self.home / ".config/quickshell"
        quickshell.mkdir(parents=True)
        (quickshell / "Native").symlink_to(external)
        manifest = profiles.capture_snapshot(self.home, self.snapshot, paths=(".config/quickshell",))
        self.assertEqual(len(manifest["dependencies"]), 1)
        (external / "Voice.qml").write_text("new upstream work")
        (quickshell / "Native").unlink()
        profiles.restore_snapshot(self.snapshot, self.home, recover_dependencies=True)
        self.assertTrue((quickshell / "Native").is_symlink())
        self.assertEqual((external / "Voice.qml").read_text(), "new upstream work")
        import shutil
        shutil.rmtree(external)
        profiles.restore_snapshot(self.snapshot, self.home, recover_dependencies=True)
        self.assertEqual((external / "Voice.qml").read_text(), "original integration")

    def test_symlink_parent_cannot_redirect_restore(self):
        self.write(".config/test", "original")
        profiles.capture_snapshot(self.home, self.snapshot, paths=(".config/test",))
        import shutil
        shutil.rmtree(self.home / ".config")
        outside = self.base / "outside"
        outside.mkdir()
        (self.home / ".config").symlink_to(outside)
        with self.assertRaisesRegex(profiles.ProfileError, "symlink parent"):
            profiles.restore_snapshot(self.snapshot, self.home)
        self.assertFalse((outside / "test").exists())

    def test_managed_file_symlink_restores_its_content_and_identity(self):
        actual = self.write("dotfiles/config.conf", "original linked config")
        link = self.home / ".config/linked.conf"
        link.parent.mkdir(parents=True)
        link.symlink_to(actual)
        profiles.capture_snapshot(self.home, self.snapshot, paths=(".config/linked.conf",))
        actual.write_text("theme changed target")
        profiles.restore_snapshot(self.snapshot, self.home)
        self.assertTrue(link.is_symlink())
        self.assertEqual(actual.read_text(), "original linked config")

    def test_stable_parent_symlink_is_supported(self):
        actual = self.write("dotfiles/gtk/settings.ini", "original GTK")
        link = self.home / ".config/gtk-3.0"
        link.parent.mkdir(parents=True)
        link.symlink_to(actual.parent)
        profiles.capture_snapshot(self.home, self.snapshot, paths=(".config/gtk-3.0/settings.ini",))
        actual.write_text("Sumi GTK")
        profiles.restore_snapshot(self.snapshot, self.home)
        self.assertTrue(link.is_symlink())
        self.assertEqual(actual.read_text(), "original GTK")

    def test_parent_and_child_snapshot_never_writes_through_staged_symlink(self):
        actual = self.write("dotfiles/ghostty/config", "live original")
        link = self.home / ".config/ghostty"
        link.parent.mkdir(parents=True)
        link.symlink_to(actual.parent)
        profiles.capture_snapshot(self.home, self.snapshot,
                                  paths=(".config/ghostty", ".config/ghostty/config", ".config/ghostty/config.ghostty"))
        self.assertEqual(actual.read_text(), "live original")
        self.assertFalse((actual.parent / "config.ghostty").exists())
        self.assertEqual(profiles.snapshot_object(self.snapshot, ".config/ghostty/config").read_text(), "live original")
        actual.write_text("live changed")
        profiles.restore_snapshot(self.snapshot, self.home)
        self.assertTrue(link.is_symlink())
        self.assertEqual(actual.read_text(), "live original")

    def test_unsafe_relative_paths_are_rejected(self):
        with self.assertRaises(profiles.ProfileError):
            profiles.capture_snapshot(self.home, self.snapshot, paths=("../other",))
        self.assertFalse(self.snapshot.exists())


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.state = self.home / ".local/state/sumi"
        self.env = patch.dict(os.environ, {"SUMI_DRY_RUN": "1", "SUMI_HOME": str(self.home)}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.write(".config/hypr/config/autostart.lua", '''hl.on("hyprland.start", function()
    hl.exec_cmd("gnome-keyring-daemon --start --components=secrets")
    hl.exec_cmd("qs -n")
    hl.exec_cmd("/usr/bin/eww --force-wayland open clock_window")
    hl.exec_cmd("/home/test/.config/thursday/session-start.sh")
end)
''')
        self.original_bindings = '''local quickshellBar = "/usr/bin/qs ipc call bar"
hl.bind("SHIFT_R", hl.dsp.exec_cmd(quickshellBar .. " toggle"))
hl.bind("SHIFT_R", hl.dsp.exec_cmd(quickshellBar .. " hide"), {release=true})
hl.bind("SUPER + SPACE", hl.dsp.exec_cmd(theme.menu))
hl.bind("SUPER + T", hl.dsp.exec_cmd("pkill qs; qs &"))
'''
        self.write(".config/hypr/config/keybinds.lua", self.original_bindings)
        self.write(".config/quickshell/shell.qml", "// Classic shell")
        self.write(".config/ghostty/config", "# Classic terminal")
        fake = types.ModuleType("sumi.themes")
        fake.DEFAULT_THEME_ID = "sunset-shrine"

        def apply(theme_id, *, home, state_dir, dry_run=False):
            self.assertFalse(dry_run)
            self.write(".config/ghostty/config", f"# Sumi terminal {theme_id}")
            profiles._json(state_dir / "theme.json", {"id": theme_id})
            return {"theme": {"id": theme_id}, "reload_commands": [], "wallpaper": None}

        fake.apply_theme = apply
        fake.apply_custom_accent = lambda *args, **kwargs: apply(args[0], **kwargs)
        self.theme_patch = patch.dict(sys.modules, {"sumi.themes": fake})
        self.theme_patch.start()
        self.addCleanup(self.theme_patch.stop)

    def write(self, relative, text):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def install(self):
        return profiles.install(home=self.home, state_dir=self.state)

    def switch(self, profile):
        return profiles.use_profile(profile, home=self.home, state_dir=self.state)

    def assert_classic_bindings_preserved(self):
        from sumi.hyprland import classic_bindings
        text = (self.home / ".config/hypr/config/keybinds.lua").read_text()
        expected = classic_bindings(self.original_bindings, str(self.home / ".local/bin/desktopctl"))
        self.assertEqual(text.split(profiles.PROFILE_SWITCH_START)[0].rstrip(), expected.rstrip())
        self.assertEqual(text.count(profiles.PROFILE_SWITCH_START), 1)
        self.assertEqual(text.count(profiles.PROFILE_SWITCH_END), 1)

    def test_install_is_neutral_and_original_cannot_be_replaced(self):
        self.install()
        self.assertEqual(profiles.profile_status(home=self.home, state_dir=self.state)["profile"], "classic")
        self.assert_classic_bindings_preserved()
        manifest_before = (self.state / "original/manifest.json").read_bytes()
        self.write(".config/ghostty/config", "later change")
        self.install()
        self.assertEqual((self.state / "original/manifest.json").read_bytes(), manifest_before)
        self.assertTrue((self.home / ".local/bin/desktopctl").stat().st_mode & stat.S_IXUSR)

    def test_profile_round_trip_preserves_each_profiles_later_edits(self):
        self.install()
        self.write(".config/ghostty/config", "Classic customization")
        self.switch("sumi")
        startup = (self.home / ".config/hypr/config/autostart.lua").read_text()
        self.assertIn("gnome-keyring-daemon", startup)
        self.assertIn("thursday/session-start.sh", startup)
        self.assertIn("session-start", startup)
        self.assertNotIn('hl.exec_cmd("qs -n")', startup)
        bindings = (self.home / ".config/hypr/config/keybinds.lua").read_text()
        self.assertIn("generated/shortcuts.lua", bindings)
        shortcut_helper = (self.home / ".config/sumi/generated/shortcuts.lua").read_text()
        self.assertIn("ipc bar", shortcut_helper)
        self.assertIn('" peek"', shortcut_helper)
        self.assertNotIn("pkill qs", bindings)
        self.write(".config/quickshell/user-customization", "saved Sumi integration change")
        self.switch("classic")
        self.assertEqual((self.home / ".config/ghostty/config").read_text(), "Classic customization")
        self.assertFalse((self.home / ".config/quickshell/user-customization").exists())
        self.assert_classic_bindings_preserved()
        self.switch("sumi")
        self.assertEqual((self.home / ".config/quickshell/user-customization").read_text(), "saved Sumi integration change")
        self.assertEqual(profiles.profile_status(home=self.home, state_dir=self.state)["profile"], "sumi")
        self.assertFalse((self.state / "transaction.json").exists())

    def test_failed_shell_readiness_restores_files_and_selected_profile(self):
        self.install()
        with patch.object(profiles, "_wait_ready", side_effect=profiles.ProfileError("not ready")):
            with self.assertRaisesRegex(profiles.ProfileError, "classic was restored"):
                self.switch("sumi")
        self.assertEqual((self.home / ".config/ghostty/config").read_text(), "# Classic terminal")
        self.assert_classic_bindings_preserved()
        self.assertFalse((self.home / ".config/systemd/user/swaync.service").exists())
        self.assertEqual(profiles.profile_status(home=self.home, state_dir=self.state)["profile"], "classic")
        self.assertFalse((self.state / "transaction.json").exists())

    def test_original_restoration_does_not_reuse_mutable_classic_snapshot(self):
        self.install()
        self.write(".config/ghostty/config", "Classic edit after install")
        self.switch("sumi")
        profiles.restore_original(home=self.home, state_dir=self.state)
        self.assertEqual((self.home / ".config/ghostty/config").read_text(), "# Classic terminal")
        self.assertEqual(profiles.profile_status(home=self.home, state_dir=self.state)["profile"], "classic")

    def test_shared_switch_survives_toggle_round_trip_and_original_restore(self):
        self.install()
        original = self.state / "original"
        before = (original / "manifest.json").read_bytes()
        archived_bindings = profiles.snapshot_object(original, ".config/hypr/config/keybinds.lua")
        self.assertEqual(archived_bindings.read_text(), self.original_bindings)
        for expected in ("sumi", "classic", "sumi"):
            self.assertEqual(self.switch("toggle")["profile"], expected)
            text = (self.home / ".config/hypr/config/keybinds.lua").read_text()
            self.assertEqual(text.count(profiles.PROFILE_SWITCH_START), 1)
            self.assertEqual(text.count(profiles.PROFILE_SWITCH_END), 1)
        profiles.restore_original(home=self.home, state_dir=self.state)
        self.assert_classic_bindings_preserved()
        helper = self.home / ".config/sumi/shared/profile-switch.lua"
        self.assertEqual(helper.read_text().count('hl.bind("SUPER + CTRL + ALT + S"'), 1)
        desktop = (self.home / ".local/share/applications/sumi-switch-desktop.desktop").read_text()
        self.assertIn("Name=Switch desktop (Classic / Sumi)", desktop)
        self.assertIn('" profile toggle\n', desktop)
        self.assertEqual((original / "manifest.json").read_bytes(), before)
        self.assertEqual(archived_bindings.read_text(), self.original_bindings)
        profiles.verify_snapshot(original)

    def test_shared_switch_install_is_idempotent_and_does_not_grow_bindings(self):
        self.install()
        bindings = self.home / ".config/hypr/config/keybinds.lua"
        before = bindings.read_text()
        self.install()
        self.switch("classic")
        self.assertEqual(bindings.read_text(), before)
        self.assert_classic_bindings_preserved()

    def test_incomplete_shared_switch_marker_refuses_overwrite(self):
        damaged = self.original_bindings + profiles.PROFILE_SWITCH_START + "\nuser content\n"
        path = self.write(".config/hypr/config/keybinds.lua", damaged)
        with self.assertRaisesRegex(profiles.ProfileError, "markers"):
            profiles._install_profile_switch(self.home)
        self.assertEqual(path.read_text(), damaged)
        self.assertFalse((self.home / ".config/sumi/shared/profile-switch.lua").exists())

    def test_cli_toggle_uses_current_profile_inside_the_locked_transition(self):
        from sumi.cli import main
        from io import StringIO
        self.install()
        with patch("sys.stdout", new_callable=StringIO):
            self.assertEqual(main(["profile", "toggle"]), 0)
        self.assertEqual(profiles.profile_status(home=self.home, state_dir=self.state)["profile"], "sumi")
        with patch("sys.stdout", new_callable=StringIO):
            self.assertEqual(main(["profile", "toggle"]), 0)
        self.assertEqual(profiles.profile_status(home=self.home, state_dir=self.state)["profile"], "classic")

    def test_cli_ipc_preserves_launcher_target_method_and_argument(self):
        from sumi.cli import main
        from io import StringIO
        with patch.object(profiles, "ipc", return_value="") as ipc, patch("sys.stdout", new_callable=StringIO):
            self.assertEqual(main(["ipc", "sumi", "toggle", "launcher"]), 0)
        ipc.assert_called_once_with("sumi", "toggle", ["launcher"], home=self.home, state_dir=self.state)

    def test_interrupted_switch_recovery_restores_journaled_state(self):
        self.install()
        current = profiles.profile_status(home=self.home, state_dir=self.state)
        snapshot = self.state / "transactions/interrupted"
        profiles.capture_snapshot(self.home, snapshot)
        profiles._record_runtime(self.state, snapshot)
        profiles._json(self.state / "transaction.json", {"from": "classic", "to": "sumi", "snapshot": str(snapshot), "previous_state": current})
        self.write(".config/ghostty/config", "half-written transition")
        with self.assertRaisesRegex(profiles.ProfileError, "interrupted switch"):
            self.switch("sumi")
        profiles.restore_pending(home=self.home, state_dir=self.state)
        self.assertEqual((self.home / ".config/ghostty/config").read_text(), "# Classic terminal")
        self.assertFalse((self.state / "transaction.json").exists())

    def test_live_theme_failure_restores_files_and_runtime(self):
        self.install()
        profiles._json(self.state / "theme.json", {"id": "before"})
        with patch.object(profiles, "_apply_theme_effects", side_effect=profiles.ProfileError("wallpaper failed")):
            with self.assertRaisesRegex(profiles.ProfileError, "previous files and wallpaper restored"):
                profiles.apply_theme_live("new", home=self.home, state_dir=self.state)
        self.assertEqual((self.home / ".config/ghostty/config").read_text(), "# Classic terminal")
        self.assertEqual(json.loads((self.state / "theme.json").read_text()), {"id": "before"})

    def test_interrupted_theme_recovery_restores_runtime_variants_and_files(self):
        self.install()
        profiles._json(self.state / "theme.json", {"id": "before"})
        profiles._json(self.state / "themes/before-custom.json", {"id": "before-custom"})
        snapshot = self.state / "theme-transactions/interrupted"
        profiles.capture_snapshot(self.home, snapshot)
        profiles._record_runtime(self.state, snapshot)
        profiles._record_variants(self.state, snapshot)
        profiles._json(self.state / "transaction.json", {"kind": "theme", "from": "classic", "to": "classic", "snapshot": str(snapshot),
                                                         "previous_state": {"profile": "classic", "installed": True}})
        self.write(".config/ghostty/config", "half-written theme")
        profiles._json(self.state / "theme.json", {"id": "partial"})
        profiles._json(self.state / "themes/new-custom.json", {"id": "new-custom"})
        profiles.restore_pending(home=self.home, state_dir=self.state)
        self.assertEqual((self.home / ".config/ghostty/config").read_text(), "# Classic terminal")
        self.assertEqual(json.loads((self.state / "theme.json").read_text()), {"id": "before"})
        self.assertFalse((self.state / "themes/new-custom.json").exists())
        self.assertTrue((self.state / "themes/before-custom.json").exists())
        self.assertFalse((self.state / "transaction.json").exists())

    def test_successful_theme_removes_durable_journal(self):
        self.install()
        profiles.apply_theme_live("next", home=self.home, state_dir=self.state)
        self.assertEqual(json.loads((self.state / "theme.json").read_text()), {"id": "next"})
        self.assertFalse((self.state / "transaction.json").exists())

    def test_sumi_surfaces_restore_translucency_and_classic_general_is_exact(self):
        original = """hl.config({
  general = { gaps_in = 10 },
  decoration = {
    active_opacity = 0.85,
    inactive_opacity = 0.8,
    blur = { enabled = true, size = 6, passes = 3 },
  },
  animations = { enabled = true },
})
"""
        self.write(".config/hypr/config/general.lua", original)
        (self.home / ".config/hypr/config/general.lua").chmod(0o640)
        self.install()
        self.switch("sumi")
        generated = (self.home / ".config/hypr/config/general.lua").read_text()
        self.assertIn("active_opacity = 0.85", generated)
        self.assertIn("inactive_opacity = 0.8", generated)
        self.assertIn("blur = { enabled = true, size = 6, passes = 3 }", generated)
        self.assertEqual(generated.count("-- >>> SUMI SURFACES START"), 1)
        self.assertEqual((self.home / ".config/hypr/config/general.lua").stat().st_mode & 0o777, 0o640)
        self.assertIn("gaps_in = 10", generated)
        self.assertIn('namespace = "^sumi-overlay$"', generated)
        self.assertIn("no_anim = true, blur = false", generated)
        self.switch("classic")
        self.assertEqual((self.home / ".config/hypr/config/general.lua").read_text(), original)

    def test_retention_keeps_latest_five_pending_original_and_profile_roots(self):
        self.install()
        original_before = (self.state / "original/manifest.json").read_bytes()
        saved = self.state / "profiles/classic/keep"
        saved.parent.mkdir(parents=True)
        saved.write_text("saved profile")
        for directory in ("transactions", "theme-transactions"):
            for index in range(8):
                snapshot = self.state / directory / f"20261021T00000{index}.000000Z"
                snapshot.mkdir(parents=True)
                (snapshot / "manifest.json").write_text("{}")
        pending = self.state / "transactions/20261021T000000.000000Z"
        profiles._json(self.state / "transaction.json", {"snapshot": str(pending)})
        profiles._prune_snapshots(self.state)
        self.assertEqual(len(list((self.state / "transactions").iterdir())), 6)
        self.assertEqual(len(list((self.state / "theme-transactions").iterdir())), 5)
        self.assertTrue(pending.exists())
        self.assertEqual((self.state / "original/manifest.json").read_bytes(), original_before)
        self.assertEqual(saved.read_text(), "saved profile")

    def test_theme_commit_automatically_bounds_its_completed_backups(self):
        self.install()
        for index in range(7):
            profiles.apply_theme_live(f"theme-{index}", home=self.home, state_dir=self.state)
        self.assertEqual(len(list((self.state / "theme-transactions").iterdir())), 5)
        self.assertFalse((self.state / "transaction.json").exists())

    def test_inactive_service_replaces_only_its_leftover_preview_before_start(self):
        commands = []
        def run(argv, **kwargs):
            commands.append(argv)
            if argv[:3] == ["systemctl", "--user", "is-active"]:
                return subprocess.CompletedProcess(argv, 3, "inactive\n", "")
            return subprocess.CompletedProcess(argv, 0, "", "")
        with patch.object(profiles, "_run", side_effect=run), patch.object(profiles, "_wait_ready"):
            profiles._start_sumi(self.home, self.state)
        kill = ["qs", "kill", "-p", str(profiles.shell_path())]
        start = ["systemctl", "--user", "start", "sumi-shell.service"]
        self.assertLess(commands.index(kill), commands.index(start))
        self.assertFalse(any(command[0] == "pkill" for command in commands))

    def test_active_service_is_not_killed_when_start_is_requested_again(self):
        commands = []
        def run(argv, **kwargs):
            commands.append(argv)
            output = "active\n" if argv[:3] == ["systemctl", "--user", "is-active"] else ""
            return subprocess.CompletedProcess(argv, 0, output, "")
        with patch.object(profiles, "_run", side_effect=run), patch.object(profiles, "_wait_ready"):
            profiles._start_sumi(self.home, self.state)
        self.assertFalse(any(command[:2] == ["qs", "kill"] for command in commands))

    def test_direct_ghostty_reload_requires_exact_executable_and_usr2_handler(self):
        proc = self.home / "proc"
        executable = self.write("bin/ghostty", "fake executable")
        other = self.write("bin/other", "unrelated executable")
        for pid, program, caught in ((11, executable, 1 << (signal.SIGUSR2 - 1)), (12, executable, 0), (13, other, 1 << (signal.SIGUSR2 - 1))):
            process = proc / str(pid)
            process.mkdir(parents=True)
            (process / "exe").symlink_to(program)
            (process / "status").write_text(f"SigCgt:\t{caught:016x}\n")
        with patch.dict(os.environ, {"SUMI_DRY_RUN": "0"}), patch("shutil.which", return_value=str(executable)), \
                patch("os.pidfd_open", return_value=101) as opened, patch("signal.pidfd_send_signal") as sent, patch("os.close") as closed:
            report = profiles._reload_ghostty(proc_dir=proc)
        self.assertEqual(report["reloaded"], [11])
        opened.assert_called_once_with(11, 0)
        sent.assert_called_once_with(101, signal.SIGUSR2, None, 0)
        closed.assert_called_once_with(101)

    def test_ghostty_identity_is_rechecked_after_opening_pidfd(self):
        proc = self.home / "proc/11"
        proc.mkdir(parents=True)
        executable = self.write("bin/ghostty", "fake executable")
        with patch.dict(os.environ, {"SUMI_DRY_RUN": "0"}), patch("shutil.which", return_value=str(executable)), \
                patch.object(profiles, "_ghostty_ready_process", side_effect=[True, False]), \
                patch("os.pidfd_open", return_value=101), patch("signal.pidfd_send_signal") as sent, patch("os.close") as closed:
            report = profiles._reload_ghostty(proc_dir=proc.parent)
        self.assertEqual(report["reloaded"], [])
        sent.assert_not_called()
        closed.assert_called_once_with(101)

    def test_theme_effects_never_start_or_reload_vendor_ghostty_service(self):
        command = ["systemctl", "--user", "reload", "app-com.mitchellh.ghostty.service"]
        report = {"reload_commands": [command]}
        with patch.object(profiles, "_run") as run, patch.object(profiles, "_reload_ghostty", return_value={"reloaded": [11], "warnings": []}):
            profiles._apply_theme_effects(report)
        self.assertFalse(any(call.args[0] == command for call in run.call_args_list))
        self.assertEqual(report["terminal_reload"]["reloaded"], [11])

    def test_theme_wallpaper_animates_by_default_with_a_bounded_grow_transition(self):
        report = {"wallpaper": self.home / "wallpaper.png"}
        with patch.object(profiles, "_run") as run, patch.object(profiles, "_apply_desktop_preferences"):
            profiles._apply_theme_effects(report, state_dir=self.state)
        run.assert_called_once_with(["awww", "img", "--transition-type", "grow",
                                    "--transition-duration", "0.65", "--transition-fps", "60",
                                    "--transition-bezier", "0.16,1,0.3,1", str(report["wallpaper"])], dry_run=False)

    def test_theme_wallpaper_honors_reduced_motion_from_the_supplied_state_root(self):
        profiles._json(self.state / "settings.json", {"reducedMotion": True})
        report = {"wallpaper": self.home / "wallpaper.png"}
        with patch.object(profiles, "_run") as run, patch.object(profiles, "_apply_desktop_preferences"):
            profiles._apply_theme_effects(report, state_dir=self.state)
        run.assert_called_once_with(["awww", "img", "--transition-type", "none", str(report["wallpaper"])], dry_run=False)

    def test_theme_effects_without_state_use_report_motion_preference_without_host_reads(self):
        report = {"wallpaper": "/tmp/wallpaper.png", "reducedMotion": True}
        with patch.object(profiles, "_run") as run, patch.object(profiles, "_apply_desktop_preferences"), \
                patch.object(profiles, "_load", side_effect=AssertionError("Unexpected host settings read")):
            profiles._apply_theme_effects(report)
        run.assert_called_once_with(["awww", "img", "--transition-type", "none", "/tmp/wallpaper.png"], dry_run=False)

    def test_polkit_is_started_without_changing_its_enablement(self):
        commands = []
        def run(argv, **kwargs):
            commands.append(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")
        with patch.object(profiles, "_run", side_effect=run):
            profiles._start_sumi(self.home, self.state)
            profiles._service_restore({"plasma-polkit-agent.service": {"active": "inactive"}})
        self.assertIn(["systemctl", "--user", "start", "plasma-polkit-agent.service"], commands)
        self.assertIn(["systemctl", "--user", "stop", "plasma-polkit-agent.service"], commands)
        self.assertFalse(any(command[2] in {"enable", "disable"} and command[-1] == "plasma-polkit-agent.service" for command in commands))

    def test_tty_recovery_selects_graphical_session_without_unlocking(self):
        def run(argv, **kwargs):
            if argv[:3] == ["systemctl", "--user", "show-environment"]:
                return subprocess.CompletedProcess(argv, 0, "XDG_SESSION_ID=graphical\nWAYLAND_DISPLAY=wayland-1\n", "")
            if argv[:2] == ["loginctl", "list-sessions"]:
                return subprocess.CompletedProcess(argv, 0, f"graphical {os.getuid()} user seat0\n", "")
            if argv[:2] == ["loginctl", "show-session"]:
                text = "Type=tty\n" if argv[2] == "tty" else f"Type=wayland\nUser={os.getuid()}\nActive=yes\nLockedHint=no\n"
                return subprocess.CompletedProcess(argv, 0, text, "")
            if argv[0] == "pgrep":
                return subprocess.CompletedProcess(argv, 1, "", "")
            raise AssertionError(argv)
        with patch.dict(os.environ, {"SUMI_DRY_RUN": "0", "XDG_SESSION_ID": "tty"}), patch.object(profiles, "_run", side_effect=run):
            profiles._assert_unlocked()
            self.assertEqual(os.environ["XDG_SESSION_ID"], "graphical")
            self.assertEqual(os.environ["WAYLAND_DISPLAY"], "wayland-1")

    def test_ui_switch_delegates_before_touching_the_shell_owner(self):
        from sumi.cli import main
        from io import StringIO
        with patch.object(profiles, "in_shell_cgroup", return_value=True), \
                patch.object(profiles, "delegate_controller", return_value={"scheduled": True}) as delegated, \
                patch.object(profiles, "use_profile") as switched, patch("sys.stdout", new_callable=StringIO):
            self.assertEqual(main(["profile", "use", "classic"]), 0)
        delegated.assert_called_once()
        switched.assert_not_called()

    def test_ui_toggle_delegates_before_stopping_its_shell(self):
        from sumi.cli import main
        from io import StringIO
        with patch.object(profiles, "in_shell_cgroup", return_value=True), \
                patch.object(profiles, "delegate_controller", return_value={"scheduled": True}) as delegated, \
                patch.object(profiles, "use_profile") as switched, patch("sys.stdout", new_callable=StringIO):
            self.assertEqual(main(["profile", "toggle"]), 0)
        self.assertEqual(delegated.call_args.args[0], ["profile", "toggle"])
        switched.assert_not_called()

    def test_lock_state_failure_refuses_switch_before_mutation(self):
        self.install()
        with patch.object(profiles, "_assert_unlocked", side_effect=profiles.ProfileError("desktop locked")):
            with self.assertRaisesRegex(profiles.ProfileError, "locked"):
                self.switch("sumi")
        self.assertFalse((self.state / "transaction.json").exists())
        self.assert_classic_bindings_preserved()

    def test_failed_classic_cutover_stops_both_owners_before_sumi_rollback(self):
        self.install()
        self.switch("sumi")
        events = []
        with patch.object(profiles, "_stop_sumi", side_effect=lambda **kw: events.append("stop-sumi")), \
                patch.object(profiles, "_stop_classic", side_effect=lambda *a, **kw: events.append("stop-classic")), \
                patch.object(profiles, "_start_sumi", side_effect=lambda *a, **kw: events.append("start-sumi")), \
                patch.object(profiles, "_start_classic", side_effect=lambda *a, **kw: events.append("start-classic")), \
                patch.object(profiles, "_restore_desktop_state", side_effect=[profiles.ProfileError("preference restore failed"), None]):
            with self.assertRaisesRegex(profiles.ProfileError, "sumi was restored"):
                self.switch("classic")
        self.assertEqual(events, ["stop-sumi", "start-classic", "stop-sumi", "stop-classic", "start-sumi"])
        self.assertEqual(profiles.profile_status(home=self.home, state_dir=self.state)["profile"], "sumi")

    def test_lua_idle_logout_qt_and_motion_round_trip(self):
        from sumi.hyprland import migrate_shell_commands
        idle = "on-timeout = hyprctl dispatch dpms off\non-resume = hyprctl dispatch dpms on && brightnessctl -r\n"
        logout = '#!/bin/sh\n"$HOME/.config/hypr/scripts/safe-close-apps.sh"\nhyprctl dispatch exit\n'
        env = 'hl.env("QT_QPA_PLATFORM", "wayland")\n'
        self.write(".config/hypr/hypridle.conf", idle)
        self.write(".config/hypr/scripts/safe-logout.sh", logout).chmod(0o755)
        self.write(".config/hypr/config/env.lua", env)
        self.install()
        self.switch("sumi")
        self.assertIn("hl.dsp.dpms", (self.home / ".config/hypr/hypridle.conf").read_text())
        self.assertIn("hl.dsp.exit()", (self.home / ".config/hypr/scripts/safe-logout.sh").read_text())
        self.assertEqual((self.home / ".config/hypr/scripts/safe-logout.sh").stat().st_mode & 0o777, 0o755)
        self.assertIn('"QT_QPA_PLATFORMTHEME", "qt6ct"', (self.home / ".config/hypr/config/env.lua").read_text())
        self.assertIn("generated/motion.lua", (self.home / ".config/hypr/config/general.lua").read_text())
        profiles.apply_motion("reduced", home=self.home, state_dir=self.state)
        self.switch("classic")
        self.assertEqual((self.home / ".config/hypr/hypridle.conf").read_text(), migrate_shell_commands(idle))
        self.assertEqual((self.home / ".config/hypr/scripts/safe-logout.sh").read_text(), migrate_shell_commands(logout))
        self.assertEqual(profiles.snapshot_object(self.state / "original", ".config/hypr/hypridle.conf").read_text(), idle)
        self.assertEqual((self.home / ".config/hypr/config/env.lua").read_text(), env)
        self.switch("sumi")
        self.assertIn("motion: reduced", (self.home / ".config/sumi/generated/motion.lua").read_text())

    def test_new_managed_file_gets_supplemental_original_without_rewriting_old_backup(self):
        from sumi.hyprland import migrate_shell_commands
        logout = "#!/bin/sh\nhyprctl dispatch exit\n"
        self.write(".config/hypr/scripts/safe-logout.sh", logout)
        original = self.state / "backups/old-original"
        profiles.capture_snapshot(self.home, original, paths=[p for p in profiles.MANAGED_PATHS if p != ".config/hypr/scripts/safe-logout.sh"], immutable=True)
        (self.state / "original").symlink_to("backups/old-original", target_is_directory=True)
        before = (original / "manifest.json").read_bytes()
        self.install()
        self.switch("sumi")
        profiles.restore_original(home=self.home, state_dir=self.state)
        self.assertEqual((self.home / ".config/hypr/scripts/safe-logout.sh").read_text(), migrate_shell_commands(logout))
        self.assertEqual((original / "manifest.json").read_bytes(), before)
        self.assertEqual(len(list((self.state / "original-additions").iterdir())), 1)

    def test_same_classic_upgrade_backs_up_new_managed_path_before_migration(self):
        from sumi.hyprland import migrate_shell_commands
        relative = ".config/hypr/scripts/safe-logout.sh"
        logout = "#!/bin/sh\nhyprctl dispatch exit\n"
        self.write(relative, logout).chmod(0o750)
        original = self.state / "backups/old-original"
        profiles.capture_snapshot(self.home, original,
                                  paths=[path for path in profiles.MANAGED_PATHS if path != relative], immutable=True)
        (self.state / "original").symlink_to("backups/old-original", target_is_directory=True)
        profiles._json(self.state / "profile.json", {"profile": "classic", "installed": True})
        before = (original / "manifest.json").read_bytes()

        self.switch("classic")
        # This second backup attempt must keep the pre-upgrade bytes captured
        # by the same-profile request, even though the live script is migrated.
        profiles.ensure_original(self.home, self.state)
        additions = list((self.state / "original-additions").iterdir())
        self.assertEqual(len(additions), 1)
        archived = profiles.snapshot_object(additions[0], relative)
        self.assertEqual(archived.read_text(), logout)
        self.assertEqual(stat.S_IMODE(archived.stat().st_mode), 0o750)
        self.assertEqual((self.home / relative).read_text(), migrate_shell_commands(logout))
        self.assertEqual((original / "manifest.json").read_bytes(), before)
        profiles.verify_snapshot(original)
        profiles.verify_snapshot(additions[0])


if __name__ == "__main__":
    unittest.main()
