import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from sumi import hyprland, operations, profiles, shortcuts
from sumi.cli import main


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name) / "home"
        self.home.mkdir()
        self.state = self.home / ".local/state/sumi"
        environment = patch.dict(os.environ, {"SUMI_HOME": str(self.home), "SUMI_STATE_DIR": str(self.state), "SUMI_DRY_RUN": "1"})
        environment.start()
        self.addCleanup(environment.stop)

    def test_delegation_persists_receipt_before_launching_independent_controller(self):
        def launch(command, **kwargs):
            operation_id = command[-1]
            record = operations.status(operation_id, self.state)
            self.assertEqual(record["status"], "queued")
            self.assertEqual(record["command"], ["restart"])
            self.assertEqual(command[-3:-1], ["operation", "run"])
            self.assertIn("--setenv=SUMI_CONTROLLER=1", command)
            return subprocess.CompletedProcess(command, 0, "", "")
        with patch.object(profiles, "_run", side_effect=launch):
            result = profiles.delegate_controller(["restart"], home=self.home, state_dir=self.state)
        self.assertTrue(result["scheduled"])
        self.assertEqual(result["id"], result["operation_id"])
        self.assertEqual((self.state / "operations" / (result["id"] + ".json")).stat().st_mode & 0o777, 0o600)

    def test_delegation_launch_failure_is_queryable(self):
        with patch.object(profiles, "_run", side_effect=profiles.ProfileError("user service unavailable")):
            with self.assertRaises(profiles.ProfileError):
                profiles.delegate_controller(["restart"], home=self.home, state_dir=self.state)
        record = operations.status("latest", self.state)
        self.assertEqual(record["status"], "failed")
        self.assertIn("user service unavailable", record["error"])

    def test_operation_records_completion_after_controller_returns(self):
        queued = operations.create(["profile", "use", "classic"], self.state)
        def invoke(command):
            self.assertEqual(operations.status(queued["id"], self.state)["status"], "running")
            print(json.dumps({"profile": "classic"}))
            return 0
        result, code = operations.run(queued["id"], self.state, invoke)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["result"], {"profile": "classic"})
        self.assertEqual(operations.status("latest", self.state)["id"], queued["id"])
        self.assertEqual(operations.status("latest", self.state)["status"], "succeeded")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["operation", "status", queued["id"], "--json"]), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "succeeded")
        with self.assertRaisesRegex(RuntimeError, "already been started"):
            operations.run(queued["id"], self.state, invoke)

    def test_operation_captures_action_error_and_interruption(self):
        queued = operations.create(["restart"], self.state)
        def failed(command):
            import sys
            print("desktopctl: readiness timed out", file=sys.stderr)
            return 1
        result, code = operations.run(queued["id"], self.state, failed)
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertIn("readiness timed out", result["error"])
        other = operations.create(["restart"], self.state)
        with self.assertRaises(KeyboardInterrupt):
            operations.run(other["id"], self.state, lambda command: (_ for _ in ()).throw(KeyboardInterrupt()))
        self.assertEqual(operations.status(other["id"], self.state)["status"], "failed")

    def test_lost_controller_is_reported_after_startup_grace_period(self):
        queued = operations.create(["restart"], self.state)
        path = self.state / "operations" / (queued["id"] + ".json")
        queued.update(status="running", updated_at="2020-01-01T00:00:00+00:00")
        profiles._json(path, queued)
        with patch.dict(os.environ, {"SUMI_DRY_RUN": "0"}), patch.object(profiles, "_run", return_value=subprocess.CompletedProcess([], 0, "ActiveState=inactive\nLoadState=not-found\n", "")):
            result = operations.status(queued["id"], self.state)
        self.assertEqual(result["status"], "failed")
        self.assertIn("pending recovery", result["error"])

    def test_operation_ids_cannot_escape_state_directory(self):
        with self.assertRaisesRegex(ValueError, "Invalid operation"):
            operations.status("../../profile", self.state)

    def test_missing_latest_is_distinct_from_missing_or_corrupt_receipt(self):
        with contextlib.redirect_stderr(io.StringIO()) as error, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["operation", "status", "latest", "--json"]), 3)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(error.getvalue(), "desktopctl: No desktop operations have been recorded.\n")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["operation", "status", "a" * 32, "--json"]), 1)
        profiles._json(self.state / "operations/latest.json", {"id": ["invalid"]})
        with contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(main(["operation", "status", "latest", "--json"]), 1)
        self.assertIn("Invalid operation ID", error.getvalue())

    def test_doctor_never_reports_pending_transition_ready(self):
        profiles._json(self.state / "profile.json", {"profile": "sumi"})
        profiles._json(self.state / "transaction.json", {"from": "sumi", "to": "classic", "snapshot": "pending"})
        with patch.dict(os.environ, {"SUMI_DRY_RUN": "0"}), patch.object(profiles, "ipc", return_value="pong") as ipc, \
             patch.object(profiles, "_notifications_owned", return_value=True), patch.object(profiles, "service_state", return_value={}):
            result = profiles.doctor(home=self.home, state_dir=self.state)
        self.assertFalse(result["ready"])
        self.assertTrue(result["profile"]["pending_recovery"])
        ipc.assert_not_called()

    def test_shell_restart_delegates_without_stopping_owner(self):
        with patch.object(profiles, "in_shell_cgroup", return_value=True), \
             patch.object(profiles, "delegate_controller", return_value={"operation_id": "example", "status": "queued"}) as delegate, \
             patch.object(profiles, "restart") as restart, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["restart"]), 0)
        delegate.assert_called_once_with(["restart"], home=self.home, state_dir=self.state)
        restart.assert_not_called()

    def test_restart_cannot_race_an_existing_transition(self):
        profiles._json(self.state / "profile.json", {"profile": "sumi"})
        with profiles._operation_lock(self.state), patch.object(profiles, "_stop_sumi") as stop:
            with self.assertRaisesRegex(profiles.ProfileError, "already running"):
                profiles.restart(home=self.home, state_dir=self.state)
        stop.assert_not_called()

    def test_classic_readiness_requires_notification_owner_and_bar_ipc(self):
        def response(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, "target bar\n" if command[0] == "qs" else "u 123\n", "")
        with patch.dict(os.environ, {"SUMI_DRY_RUN": "0"}), patch.object(profiles, "_run", side_effect=response) as run:
            profiles._wait_classic_ready(self.home)
        self.assertEqual(run.call_count, 2)
        with patch.dict(os.environ, {"SUMI_DRY_RUN": "0"}), patch.object(profiles, "_run", return_value=subprocess.CompletedProcess([], 0, "", "")), \
             patch.object(profiles.time, "monotonic", side_effect=[0, 0, 16]), patch.object(profiles.time, "sleep"):
            with self.assertRaisesRegex(profiles.ProfileError, "Classic did not become ready"):
                profiles._wait_classic_ready(self.home)

    def test_binding_migration_handles_formatting_aliases_comments_and_is_idempotent(self):
        source = '''local mainMod = 'SUPER'
-- hl.bind("SUPER + SPACE", hl.dsp.exec_cmd("do-not-execute"))
hl . bind ( mainMod .. ' + SPACE', hl.dsp.exec_cmd( theme.menu ) )
hl.bind(mainMod .. " + T", hl.dsp.exec_cmd( "pkill qs; qs &" ))
hl.bind(mainMod .. " + W", hl.dsp.window.close())
'''
        executable = str(self.home / ".local/bin/desktopctl")
        result, helper = shortcuts.render_bindings(source, executable)
        self.assertNotIn("pkill qs", result)
        self.assertIn('hl.dsp.window.close()', result)
        self.assertIn("do-not-execute", result)
        self.assertIn("ipc sumi toggle launcher", helper)
        self.assertEqual(shortcuts.render_bindings(result, executable), (result, helper))
        # Compile generated output without executing any dispatcher or file.
        for content in (result, helper):
            compile_result = subprocess.run(["lua", "-e", "assert(load(io.read('*a')))"], input=content, text=True, capture_output=True)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)

    def test_binding_conflicts_and_duplicates_are_rejected(self):
        executable = str(self.home / ".local/bin/desktopctl")
        with self.assertRaisesRegex(ValueError, "conflicts"):
            shortcuts.render_bindings('hl.bind("SUPER + CTRL + V", hl.dsp.exec_cmd("custom-app"))', executable)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            shortcuts.render_bindings('hl.bind("CTRL + SUPER + B", one)\nhl.bind("SUPER + CTRL + B", two)', executable)

    def test_registry_has_unique_ids_and_contains_generated_keyboard_hub(self):
        registry = shortcuts.registry()
        self.assertEqual(len(registry["shortcuts"]), len({entry["id"] for entry in registry["shortcuts"]}))
        self.assertTrue(any(entry["keys"] == "Super + Space" and "hub" in entry["label"] for entry in registry["shortcuts"]))

    def test_hyprland_migrations_preserve_shell_chaining_and_compile_lua(self):
        original = "after_sleep_cmd = hyprctl dispatch dpms on && brightnessctl -r\non-timeout = hyprctl dispatch dpms off\n"
        migrated = hyprland.migrate_shell_commands(original)
        self.assertIn('hl.dsp.dpms({ action = "on" })', migrated)
        self.assertIn("&& brightnessctl -r", migrated)
        self.assertEqual(hyprland.migrate_shell_commands(migrated), migrated)
        logout = hyprland.migrate_shell_commands('safe-close-apps.sh\nhyprctl dispatch exit\n')
        self.assertIn("hl.dsp.exit()", logout)
        resized = hyprland.migrate_lua_commands('hl.bind("SUPER + mouse_down", hl.dsp.exec_cmd("hyprctl dispatch resizeactive 0 -20"))')
        self.assertIn("relative = true", resized)
        self.assertNotIn("hyprctl", resized)
        for mode in ("normal", "battery", "reduced"):
            result = subprocess.run(["lua", "-e", "assert(load(io.read('*a')))"], input=hyprland.motion_lua(mode) + resized, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_classic_compatibility_uses_scoped_controller_and_lua_dispatch(self):
        executable = str(self.home / ".local/bin/desktopctl")
        bindings = '''local quickshellBar = "/usr/bin/qs ipc call bar"
hl.bind("SUPER + T", hl.dsp.exec_cmd( 'pkill qs; qs &' ))
hl.bind("SUPER + mouse_down", hl.dsp.exec_cmd("hyprctl dispatch resizeactive 0 20"))
'''
        migrated = hyprland.classic_bindings(bindings, executable)
        self.assertNotIn("pkill", migrated)
        self.assertIn("hl.dsp.window.resize", migrated)
        self.assertEqual(hyprland.classic_bindings(migrated, executable), migrated)
        workspace = 'onClicked: Hyprland.dispatch("workspace " + ws.modelData)'
        migrated_workspace = hyprland.classic_workspace_qml(workspace)
        self.assertIn("hl.dsp.focus({ workspace = ", migrated_workspace)
        self.assertEqual(hyprland.classic_workspace_qml(migrated_workspace), migrated_workspace)
        power = 'activateAction: () => Quickshell.execDetached(["hyprctl", "dispatch", "exit"])'
        migrated_power = hyprland.classic_power_qml(power, executable)
        self.assertIn('"action", "power", "logout"', migrated_power)
        self.assertNotIn('"hyprctl"', migrated_power)

    def test_platform_environment_changes_cover_dbus_services_and_compositor(self):
        with patch.object(profiles, "_run", return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
            profiles._set_platform_environment("qt6ct")
            profiles._set_platform_environment(None)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn(["dbus-update-activation-environment", "--systemd", "QT_QPA_PLATFORMTHEME=qt6ct"], commands)
        self.assertIn(["systemctl", "--user", "unset-environment", "QT_QPA_PLATFORMTHEME"], commands)
        self.assertIn(["hyprctl", "eval", 'hl.env("QT_QPA_PLATFORMTHEME", "")'], commands)

    def test_compositor_configuration_errors_abort_refresh(self):
        def response(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, "invalid layer rule" if command[-1] == "configerrors" else "", "")
        with patch.object(profiles, "_run", side_effect=response):
            with self.assertRaisesRegex(profiles.ProfileError, "invalid layer rule"):
                profiles._refresh_desktop()

    def test_surface_upgrade_restores_actual_lua_defaults_and_preserves_user_preferences(self):
        original = '''
hl.config({ general = { gaps_in = 9 }, decoration = {
    active_opacity = 1.0, inactive_opacity = 0.97, fullscreen_opacity = 1.0,
    rounding = 13, shadow = { enabled = false, range = 12 },
    blur = { enabled = false, size = 4, passes = 2, vibrancy = 0.1696, noise = 0.02 },
} })
'''
        generated = profiles._sumi_general(original)
        self.assertIn(original.strip(), generated)
        self.assertEqual(profiles._sumi_general(generated), generated)
        self.assertEqual(generated.count("-- >>> SUMI SURFACES START"), 1)
        self.assertEqual(generated.count('namespace = "^sumi-overlay$"'), 1)
        harness = '''
local settings = {}
local function merge(target, changes)
    for key, value in pairs(changes) do
        if type(value) == "table" then
            target[key] = target[key] or {}; merge(target[key], value)
        else target[key] = value end
    end
end
hl = { config = function(value) merge(settings, value) end, layer_rule = function(value) end }
'''
        check = '''
local d = settings.decoration
assert(d.active_opacity == 0.85 and d.inactive_opacity == 0.8)
assert(d.blur.enabled and d.blur.size == 6 and d.blur.passes == 3)
assert(d.blur.vibrancy == 0.1696 and d.blur.noise == 0.02)
assert(d.fullscreen_opacity == 1.0 and d.rounding == 13)
assert(not d.shadow.enabled and d.shadow.range == 12 and settings.general.gaps_in == 9)
'''
        result = subprocess.run(["lua", "-"], input=harness + generated + check, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_same_sumi_profile_applies_surface_upgrade_once_without_shell_restart(self):
        profiles._json(self.state / "profile.json", {"profile": "sumi", "installed": True})
        general = self.home / ".config/hypr/config/general.lua"
        source = hyprland.motion_include("-- user preferences\n", self.home)
        profiles.atomic_write(general, source, mode=0o640)
        with patch.object(profiles, "_assert_unlocked"), patch.object(profiles, "ensure_original") as backup, \
             patch.object(profiles, "_install_profile_switch"), patch.object(profiles, "_refresh_desktop") as refresh, \
             patch.object(profiles, "_stop_sumi") as stop, patch.object(profiles, "_start_sumi") as start:
            backup.side_effect = lambda *args, **kwargs: self.assertIn("-- user preferences", general.read_text())
            self.assertTrue(profiles.use_profile("sumi", home=self.home, state_dir=self.state)["surfaces_changed"])
            self.assertFalse(profiles.use_profile("sumi", home=self.home, state_dir=self.state)["surfaces_changed"])
        refresh.assert_called_once()
        stop.assert_not_called()
        start.assert_not_called()
        self.assertEqual(general.stat().st_mode & 0o777, 0o640)
        self.assertEqual(hyprland.motion_include(general.read_text(), self.home), general.read_text())
        self.assertLess(general.read_text().index("SUMI SURFACES START"), general.read_text().index("SUMI MOTION START"))

    def test_surface_upgrade_rolls_back_bytes_and_permissions_on_reload_error(self):
        general = self.home / ".config/hypr/config/general.lua"
        original = "-- custom config\nhl.config({ decoration = { rounding = 21 } })\n"
        profiles.atomic_write(general, original, mode=0o640)
        with patch.object(profiles, "_refresh_desktop", side_effect=[profiles.ProfileError("reload failed"), None]):
            with self.assertRaisesRegex(profiles.ProfileError, "reload failed"):
                profiles._apply_sumi_surfaces(self.home)
        self.assertEqual(general.read_text(), original)
        self.assertEqual(general.stat().st_mode & 0o777, 0o640)

    def test_motion_does_not_modify_classic_and_serializes_with_transition(self):
        with patch.object(profiles, "_refresh_desktop") as refresh:
            result = profiles.apply_motion("reduced", home=self.home, state_dir=self.state)
        self.assertFalse(result["applied"])
        refresh.assert_not_called()
        self.assertFalse((self.state / "motion.json").exists())
        profiles._json(self.state / "profile.json", {"profile": "sumi"})
        with profiles._operation_lock(self.state):
            with self.assertRaisesRegex(profiles.ProfileError, "already running"):
                profiles.apply_motion("normal", home=self.home, state_dir=self.state)

    def motion_configuration(self, mode):
        # Execute the rendered Lua against recording API functions, never a
        # compositor, to verify effective curves, leaf settings and layer rules.
        harness = '''
hl = {
 config = function(value) print("enabled", tostring(value.animations.enabled)) end,
 curve = function(name, value) print("curve", name, value.points[1][1], value.points[1][2], value.points[2][1], value.points[2][2]) end,
 animation = function(value) print("animation", value.leaf, tostring(value.enabled), value.speed, value.bezier, value.style or "-") end,
 layer_rule = function(value) print("layer", value.match.namespace, tostring(value.no_anim)) end
}
'''
        result = subprocess.run(["lua", "-"], input=harness + hyprland.motion_lua(mode), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [line.split("\t") for line in result.stdout.splitlines()]
        return {
            "enabled": next(row[1] for row in rows if row[0] == "enabled"),
            "curves": {row[1]: tuple(map(float, row[2:])) for row in rows if row[0] == "curve"},
            "animations": {row[1]: (row[2], float(row[3]), row[4], row[5]) for row in rows if row[0] == "animation"},
            "layers": [tuple(row[1:]) for row in rows if row[0] == "layer"],
        }

    def test_normal_motion_restores_original_workspace_windows_and_fade_curves(self):
        motion = self.motion_configuration("normal")
        self.assertEqual(motion["enabled"], "true")
        curves = motion["curves"]
        self.assertEqual(curves["sumiEaseOutQuint"], (0.23, 1, 0.32, 1))
        self.assertEqual(curves["sumiLinear"], (0, 0, 1, 1))
        self.assertEqual(curves["sumiAlmostLinear"], (0.5, 0.5, 0.75, 1))
        self.assertEqual(curves["sumiQuick"], (0.15, 0, 0.1, 1))
        expected = {
            "border": (5.39, "sumiEaseOutQuint", "-"),
            "windows": (4.79, "sumiEaseOutQuint", "-"),
            "windowsIn": (4.1, "sumiEaseOutQuint", "popin 87%"),
            "windowsOut": (1.49, "sumiLinear", "popin 87%"),
            "fadeIn": (1.73, "sumiAlmostLinear", "-"),
            "fadeOut": (1.46, "sumiAlmostLinear", "-"),
            "fade": (3.03, "sumiQuick", "-"),
            "layers": (3.81, "sumiEaseOutQuint", "-"),
            "layersIn": (4, "sumiEaseOutQuint", "fade"),
            "layersOut": (1.5, "sumiLinear", "fade"),
            "fadeLayersIn": (1.79, "sumiAlmostLinear", "-"),
            "fadeLayersOut": (1.39, "sumiAlmostLinear", "-"),
            "workspaces": (5, "sumiEaseOutQuint", "slide"),
            "workspacesIn": (5, "sumiEaseOutQuint", "slide"),
            "workspacesOut": (5, "sumiEaseOutQuint", "slide"),
            "specialWorkspace": (5, "sumiEaseOutQuint", "slidevert bottom"),
            "zoomFactor": (7, "sumiQuick", "-"),
        }
        for leaf, values in expected.items():
            self.assertEqual(motion["animations"][leaf], ("true", *values), leaf)
        self.assertEqual(motion["layers"], [("^sumi-(bar|overlay|notifications)$", "true")])

    def test_battery_preserves_spatial_motion_and_reduced_disables_every_leaf(self):
        normal = self.motion_configuration("normal")
        battery = self.motion_configuration("battery")
        reduced = self.motion_configuration("reduced")
        self.assertEqual(battery["enabled"], "true")
        self.assertEqual(reduced["enabled"], "false")
        for leaf, settings in battery["animations"].items():
            self.assertEqual(settings[0], "true", leaf)
            self.assertLess(settings[1], normal["animations"][leaf][1], leaf)
            self.assertEqual(reduced["animations"][leaf][0], "false", leaf)
        self.assertEqual(battery["animations"]["workspaces"][3], "slide")
        self.assertEqual(battery["animations"]["specialWorkspace"][3], "slidevert bottom")
        self.assertEqual(battery["animations"]["windowsIn"][3], "popin 94%")
        self.assertEqual(battery["layers"], normal["layers"])
        self.assertEqual(reduced["layers"], normal["layers"])

    def test_same_motion_mode_rewrites_outdated_generated_content(self):
        profiles._json(self.state / "profile.json", {"profile": "sumi"})
        profiles._json(self.state / "motion.json", {"mode": "normal"})
        generated = self.home / ".config/sumi/generated/motion.lua"
        profiles.atomic_write(generated, "-- normal mode from an older generator\n")
        general = self.home / ".config/hypr/config/general.lua"
        profiles.atomic_write(general, hyprland.motion_include("-- user config\n", self.home))
        with patch.object(profiles, "_refresh_desktop") as refresh:
            self.assertTrue(profiles.apply_motion("normal", home=self.home, state_dir=self.state)["changed"])
            self.assertFalse(profiles.apply_motion("normal", home=self.home, state_dir=self.state)["changed"])
        self.assertEqual(generated.read_text(), hyprland.motion_lua("normal"))
        refresh.assert_called_once()

    def test_motion_is_persisted_idempotent_and_restored_on_reload_failure(self):
        profiles._json(self.state / "profile.json", {"profile": "sumi"})
        general = self.home / ".config/hypr/config/general.lua"
        profiles.atomic_write(general, "-- existing user configuration\n", mode=0o640)
        with patch.object(profiles, "_refresh_desktop") as refresh:
            self.assertTrue(profiles.apply_motion("reduced", home=self.home, state_dir=self.state)["changed"])
            self.assertFalse(profiles.apply_motion("reduced", home=self.home, state_dir=self.state)["changed"])
        refresh.assert_called_once()
        before = (self.home / ".config/sumi/generated/motion.lua").read_text()
        self.assertIn("enabled = false", before)
        self.assertIn("-- existing user configuration", general.read_text())
        self.assertIn("dofile", general.read_text())
        self.assertIn("motion.lua", general.read_text())
        self.assertEqual(general.stat().st_mode & 0o777, 0o640)
        # An externally generated Sumi profile may have no include yet. Failed
        # application must restore that preexisting state as well as the mode.
        general.write_text("-- profile without include\n")
        with patch.object(profiles, "_refresh_desktop", side_effect=[profiles.ProfileError("reload failed"), None]):
            with self.assertRaisesRegex(profiles.ProfileError, "reload failed"):
                profiles.apply_motion("normal", home=self.home, state_dir=self.state)
        self.assertEqual((self.home / ".config/sumi/generated/motion.lua").read_text(), before)
        self.assertEqual(json.loads((self.state / "motion.json").read_text())["mode"], "reduced")
        self.assertEqual(general.read_text(), "-- profile without include\n")


if __name__ == "__main__":
    unittest.main()
