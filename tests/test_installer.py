"""Exercise real filesystem transactions in isolated homes; external commands mocked."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from sumi.install import ownership, workflow, lifecycle, packages, prerequisites
from sumi.install.paths import InstallError, Layout

ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="sumi installer test ")
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.home = self.base / "new home"
        self.home.mkdir()
        environment = {"HOME": str(self.home), "SUMI_HOME": str(self.home),
                       "XDG_CONFIG_HOME": str(self.base / "custom config"),
                       "XDG_DATA_HOME": str(self.base / "custom data"),
                       "XDG_STATE_HOME": str(self.base / "custom state"),
                       "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                       "PYTHONDONTWRITEBYTECODE": "1"}
        self.environment = patch.dict(os.environ, environment, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.layout = Layout.from_environment()
        for target in ("sumi.install.prerequisites.check_host", "sumi.install.prerequisites.check_versions", "sumi.install.packages.check_dependencies"):
            mocked = patch(target, return_value=[])
            mocked.start()
            self.addCleanup(mocked.stop)
        self.output = io.StringIO()

    def install(self, *, update=False, choice=None, no_packages=True):
        if choice is None:
            choice = "Back up and use Sumi" if update or self.layout.config.exists() else "Install Sumi"
        with patch("builtins.input", return_value=choice), contextlib.redirect_stdout(self.output):
            return workflow.run(ROOT, home=self.home, update=update, no_packages=no_packages)

    def test_dry_run_does_not_create_home_config_state_or_call_commands(self):
        before = ownership.inventory(self.base)
        with patch("subprocess.run", side_effect=AssertionError("dry run command")), contextlib.redirect_stdout(self.output):
            result = workflow.run(ROOT, dry_run=True, home=self.home)
        self.assertTrue(result["dry_run"])
        self.assertEqual(before, ownership.inventory(self.base))

    def test_cancellation_has_zero_filesystem_and_package_effects(self):
        previous = self.layout.config / "hypr/hyprland.lua"
        previous.parent.mkdir(parents=True)
        previous.write_text("-- previous desktop\n")
        before = ownership.inventory(self.base)
        with patch("sumi.install.packages.install_packages") as packages_call:
            self.assertTrue(self.install(choice="yes", no_packages=False)["cancelled"])
        packages_call.assert_not_called()
        self.assertEqual(before, ownership.inventory(self.base))

    def test_new_collision_after_fresh_consent_stops_before_packages_or_writes(self):
        appeared = self.layout.config / "hypr/hyprland.lua"
        def answer(_prompt):
            appeared.parent.mkdir(parents=True)
            appeared.write_text("-- created while summary was open\n")
            return "Install Sumi"
        with patch("builtins.input", side_effect=answer), patch("sumi.install.packages.install_packages") as package_call, contextlib.redirect_stdout(self.output):
            with self.assertRaisesRegex(InstallError, "appeared after"):
                workflow.run(ROOT, home=self.home)
        package_call.assert_not_called()
        self.assertFalse(self.layout.records.exists())
        self.assertEqual(appeared.read_text(), "-- created while summary was open\n")

    def test_new_collision_during_package_install_is_not_overwritten(self):
        appeared = self.layout.config / "hypr/hyprland.lua"
        def package_install(_source):
            appeared.parent.mkdir(parents=True)
            appeared.write_text("-- created during package install\n")
        with patch("sumi.install.packages.install_packages", side_effect=package_install):
            with self.assertRaisesRegex(InstallError, "appeared after"):
                self.install(no_packages=False)
        self.assertFalse(self.layout.records.exists())
        self.assertEqual(appeared.read_text(), "-- created during package install\n")

    def test_cli_lifecycle_previews_do_not_delegate_or_write_operation_receipts(self):
        from sumi import cli
        self.install()
        self.install(update=True)
        before = ownership.inventory(self.base)
        for command in ("uninstall", "rollback"):
            with self.subTest(command=command), patch("sumi.profiles.in_shell_cgroup", return_value=True), patch("sumi.profiles.delegate_controller", side_effect=AssertionError("preview delegated")), contextlib.redirect_stdout(self.output):
                self.assertEqual(cli.main([command, "--dry-run"]), 0)
        self.assertEqual(before, ownership.inventory(self.base))

    def test_fresh_install_custom_xdg_spaces_and_checkout_independence(self):
        result = self.install()
        self.assertTrue(result["installed"])
        self.assertTrue((self.layout.runtime / "shell/shell.qml").is_file())
        self.assertTrue((self.layout.config / "hypr/hyprland.lua").is_file())
        self.assertFalse((self.home / ".config").exists())
        self.assertFalse(lifecycle.recovery_available(home=self.home))
        profile = ownership.load(self.layout.state / "profile.json")
        self.assertEqual(profile["profile"], "sumi")
        self.assertTrue(profile["standalone"])
        self.assertEqual(profile["install_root"], str(self.layout.runtime))
        wrapper = (self.layout.bin / "desktopctl").read_text()
        self.assertNotIn(str(ROOT), wrapper)
        theme = (self.layout.state / "theme.json").read_text()
        self.assertNotIn(str(ROOT), theme)
        self.assertIn(str(self.layout.runtime), theme)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        result = subprocess.run([str(self.layout.bin / "desktopctl"), "shortcuts"], cwd=self.base,
                                env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsInstance(json.loads(result.stdout)["shortcuts"], list)

    def test_asset_rebasing_happens_before_json_escaping_of_source_paths(self):
        from sumi import themes
        source = self.base / 'source with "quotes" and spaces'
        theme = themes.get_theme(themes.DEFAULT_THEME_ID)
        theme["wallpaper"] = str(source / "assets/wallpapers/original.png")
        theme["thumbnail"] = str(source / "assets/thumbnails/original.png")
        with patch("sumi.themes.get_theme", return_value=theme):
            artifacts = workflow.render_artifacts(source, self.layout)
        rendered = json.loads(artifacts[self.layout.state / "theme.json"][0])
        self.assertEqual(rendered["wallpaper"], str(self.layout.runtime / "assets/wallpapers/original.png"))
        self.assertNotIn(str(source), rendered["wallpaper"])

    def test_explicit_replacement_backs_up_every_artifact_and_restores_original(self):
        old = self.layout.config / "hypr/hyprland.lua"
        old.parent.mkdir(parents=True)
        old.write_text("-- old desktop\n")
        kitty = self.layout.config / "kitty/kitty.conf"
        kitty.parent.mkdir(parents=True)
        kitty.write_text("font_size 14\n")
        wrapper = self.layout.bin / "desktopctl"
        wrapper.parent.mkdir(parents=True)
        wrapper.write_text("#!/bin/sh\necho previous\n")
        wrapper.chmod(0o755)
        self.install()
        installed = ownership.load(self.layout.manifest)
        backup = ownership.checked_snapshot(self.layout, Path(installed["original"]))
        self.assertEqual(set(backup["paths"]), set(installed["artifacts"]))
        self.assertTrue(lifecycle.recovery_available(home=self.home))
        removed = lifecycle.uninstall(home=self.home)
        self.assertTrue(removed["uninstalled"])
        self.assertEqual(old.read_text(), "-- old desktop\n")
        self.assertEqual(kitty.read_text(), "font_size 14\n")
        self.assertEqual(wrapper.read_text(), "#!/bin/sh\necho previous\n")
        self.assertTrue(Path(installed["original"]).is_dir())

    def test_replacement_does_not_import_dangling_legacy_hyprland_modules(self):
        legacy = self.layout.config / "hypr/config/theme.lua"
        legacy.parent.mkdir(parents=True)
        legacy.write_text('local M = require("old_private_theme")\nreturn M\n')
        lock = self.layout.config / "hypr/hyprlock.conf"
        lock.write_text("source = old-private-lock.conf\n")
        self.install()
        self.assertFalse(legacy.exists())
        self.assertNotIn("old-private-lock", lock.read_text())
        self.assertIn("input-field", lock.read_text())
        lifecycle.uninstall(home=self.home)
        self.assertEqual(legacy.read_text(), 'local M = require("old_private_theme")\nreturn M\n')
        self.assertEqual(lock.read_text(), "source = old-private-lock.conf\n")

    def test_repeated_install_refuses_without_update(self):
        self.install()
        before = ownership.inventory(self.base)
        with self.assertRaisesRegex(InstallError, "already installed"):
            self.install()
        self.assertEqual(before, ownership.inventory(self.base))

    def test_package_failure_leaves_desktop_and_private_state_untouched(self):
        before = ownership.inventory(self.base)
        with patch("sumi.install.packages.install_packages", side_effect=InstallError("package failure")):
            with self.assertRaisesRegex(InstallError, "package failure"):
                self.install(no_packages=False)
        self.assertEqual(before, ownership.inventory(self.base))

    def test_failed_activation_restores_existing_configuration(self):
        old = self.layout.config / "hypr/hyprland.lua"
        old.parent.mkdir(parents=True)
        old.write_text("previous\n")
        original_replace = ownership.replace
        calls = 0
        def fail_once(source, destination):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("injected disk failure")
            return original_replace(source, destination)
        with patch("sumi.install.ownership.replace", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "injected"):
                self.install()
        self.assertEqual(old.read_text(), "previous\n")
        self.assertFalse(self.layout.runtime.exists())
        self.assertFalse(self.layout.manifest.exists())
        self.assertFalse(self.layout.journal.exists())

    def test_killed_install_journal_restores_on_recovery(self):
        destination = self.layout.config / "hypr"
        destination.mkdir(parents=True)
        (destination / "hyprland.lua").write_text("before kill")
        with ownership.locked(self.layout):
            backup = ownership.snapshot(self.layout, [destination], kind="simulated-kill")
            ownership.json_write(self.layout.journal, {"snapshot": str(backup)})
            (destination / "hyprland.lua").write_text("partially installed")
            self.assertTrue(ownership.recover_pending(self.layout))
        self.assertEqual((destination / "hyprland.lua").read_text(), "before kill")
        self.assertFalse(self.layout.journal.exists())

    def test_real_shell_dry_run_does_not_write_bytecode_or_xdg_state(self):
        source = self.base / "public source with spaces"
        source.mkdir()
        for name in (*workflow.RUNTIME_ENTRIES, "install.sh"):
            item = ROOT / name
            if item.is_dir():
                shutil.copytree(item, source / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(item, source / name)
        before = ownership.inventory(self.base)
        result = subprocess.run([str(source / "install.sh"), "--dry-run"], cwd=self.base,
                                env=dict(os.environ), capture_output=True, text=True, timeout=30)
        # A non-Arch test runner may report prerequisite failure; preview remains safe.
        self.assertIn("DRY RUN", result.stdout, result.stderr)
        self.assertEqual(before, ownership.inventory(self.base))

    def test_update_preserves_local_files_and_rollback_restores_prior_runtime(self):
        self.install()
        marker = self.layout.runtime / "release-version"
        marker.write_text("previous release")
        local = self.layout.config / "hypr/local.lua"
        local.write_text("-- my personal bindings\n")
        extra = self.layout.config / "hypr/machine.lua"
        extra.write_text("-- retained user addition\n")
        self.install(update=True)
        self.assertFalse(marker.exists())
        self.assertEqual(local.read_text(), "-- my personal bindings\n")
        self.assertEqual(extra.read_text(), "-- retained user addition\n")
        self.assertTrue(lifecycle.rollback(home=self.home)["restored"])
        self.assertEqual(marker.read_text(), "previous release")
        self.assertTrue(ownership.load(self.layout.manifest)["rollback"])

    def test_uninstall_preserves_edits_private_data_and_backups(self):
        self.install()
        edited = self.layout.config / "hypr/local.lua"
        edited.write_text("-- keep me\n")
        private = self.layout.state / "launcher-history.json"
        private.write_text('{"private":"learning"}')
        result = lifecycle.uninstall(home=self.home)
        self.assertIn(str(self.layout.config / "hypr"), result["preserved_edited"])
        self.assertEqual(edited.read_text(), "-- keep me\n")
        self.assertEqual(private.read_text(), '{"private":"learning"}')
        self.assertFalse(self.layout.runtime.exists())
        self.assertTrue((self.layout.records / "backups").exists())

    def test_update_does_not_take_ownership_of_user_additions(self):
        self.install()
        local = self.layout.config / "hypr/local.lua"
        local.write_text("-- user-owned override\n")
        self.install(update=True)
        result = lifecycle.uninstall(home=self.home)
        self.assertIn(str(local.parent), result["preserved_edited"])
        self.assertEqual(local.read_text(), "-- user-owned override\n")

    def test_original_recovery_saves_edits_and_removes_artifacts_added_by_updates(self):
        previous = self.layout.config / "hypr/hyprland.lua"
        previous.parent.mkdir(parents=True)
        previous.write_text("-- previous desktop\n")
        self.install()
        rendered = workflow.render_artifacts
        later_file = self.layout.config / "sumi/later-release.conf"
        def additional(*args, **kwargs):
            files = rendered(*args, **kwargs)
            files[later_file] = (b"new feature", 0o600)
            return files
        with patch("sumi.install.workflow.render_artifacts", side_effect=additional):
            self.install(update=True)
        previous.write_text("-- latest user edits\n")
        result = lifecycle.restore_previous(home=self.home)
        self.assertEqual(previous.read_text(), "-- previous desktop\n")
        self.assertFalse(later_file.exists())
        safety = Path(result["safety_snapshot"])
        saved = ownership.checked_snapshot(self.layout, safety)["paths"][str(previous.parent)]
        self.assertEqual((safety / "objects" / saved["object"] / "hyprland.lua").read_text(), "-- latest user edits\n")

    def test_uninstall_preview_makes_no_changes(self):
        self.install()
        before = ownership.inventory(self.base)
        self.assertTrue(lifecycle.uninstall(home=self.home, dry_run=True)["dry_run"])
        self.assertEqual(before, ownership.inventory(self.base))

    def test_edit_between_uninstall_review_and_lock_is_preserved(self):
        self.install()
        edited = self.layout.config / "hypr/local.lua"
        real_lock = ownership.locked
        @contextlib.contextmanager
        def edit_then_lock(layout):
            edited.write_text("-- edit raced with uninstall\n")
            with real_lock(layout):
                yield
        with patch("sumi.install.ownership.locked", side_effect=edit_then_lock):
            with self.assertRaisesRegex(InstallError, "changed during uninstall"):
                lifecycle.uninstall(home=self.home)
        self.assertEqual(edited.read_text(), "-- edit raced with uninstall\n")
        self.assertTrue(self.layout.manifest.is_file())

    def test_incomplete_uninstall_reports_pending_recovery_when_manifest_is_missing(self):
        self.layout.records.mkdir(parents=True)
        ownership.json_write(self.layout.journal, {"snapshot": "unused"})
        with self.assertRaisesRegex(InstallError, "restore pending"):
            lifecycle.uninstall(home=self.home, dry_run=True)

    def test_rollback_preview_makes_no_changes(self):
        self.install()
        self.install(update=True)
        before = ownership.inventory(self.base)
        self.assertTrue(lifecycle.rollback(home=self.home, dry_run=True)["dry_run"])
        self.assertEqual(before, ownership.inventory(self.base))

    def test_tampered_backup_blocks_uninstall_before_deleting_anything(self):
        old = self.layout.config / "hypr/hyprland.lua"
        old.parent.mkdir(parents=True)
        old.write_text("old\n")
        self.install()
        installed = ownership.load(self.layout.manifest)
        original = Path(installed["original"])
        record = ownership.load(original / "snapshot.json")["paths"][str(old.parent)]
        (original / "objects" / record["object"] / "hyprland.lua").write_text("tampered")
        before = ownership.inventory(self.base)
        with self.assertRaisesRegex(InstallError, "checksum"):
            lifecycle.uninstall(home=self.home)
        self.assertEqual(before, ownership.inventory(self.base))

    def test_destination_symlink_parent_is_rejected_without_writes(self):
        self.layout.config.mkdir()
        external = self.base / "external"
        external.mkdir()
        (self.layout.config / "kitty").symlink_to(external, target_is_directory=True)
        before = ownership.inventory(self.base)
        with self.assertRaisesRegex(InstallError, "symlink"):
            self.install()
        self.assertEqual(before, ownership.inventory(self.base))

    def test_collision_symlink_is_backed_up_without_following_external_target(self):
        self.layout.config.mkdir()
        external = self.base / "external hypr"
        external.mkdir()
        (external / "hyprland.lua").write_text("external\n")
        hypr = self.layout.config / "hypr"
        hypr.symlink_to(external, target_is_directory=True)
        self.install()
        self.assertFalse(hypr.is_symlink())
        lifecycle.uninstall(home=self.home)
        self.assertTrue(hypr.is_symlink())
        self.assertEqual((external / "hyprland.lua").read_text(), "external\n")


class PackageTests(unittest.TestCase):
    def test_only_official_packages_and_full_upgrade_are_planned(self):
        command = packages.package_command(ROOT)
        self.assertEqual(command[:6], ["sudo", "pacman", "-Syu", "--needed", "--", "core/python"])
        self.assertNotIn("--noconfirm", command)
        self.assertTrue(all(name.startswith(("core/", "extra/")) for name in command[5:]))

    def test_package_errors_are_actionable(self):
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, ["pacman"])), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(InstallError, "Desktop files were not changed"):
                packages.install_packages(ROOT)

    def test_version_rejects_pre_lua_hyprland(self):
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "Hyprland v0.54.0", "")):
            self.assertIn("hyprland", prerequisites.check_versions()[0])

    def test_no_bluetooth_hardware_skips_service(self):
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1)), patch.object(Path, "is_dir", return_value=False), contextlib.redirect_stdout(io.StringIO()):
            notes = packages.configure_system_services()
        self.assertTrue(any("No Bluetooth" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
