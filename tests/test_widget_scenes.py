"""Wallpaper geometry and transactional scene commits without a live desktop."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from sumi import profiles, scenes, themes


class WidgetSceneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.state = self.base / "state"
        self.environment = patch.dict(os.environ, {
            "SUMI_STATE_DIR": str(self.state), "SUMI_DATA_DIR": str(self.base / "data"),
            "SUMI_HOME": str(self.home), "SUMI_DRY_RUN": "1",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.theme = themes.get_theme("torii-dawn")

    def test_every_bundled_image_has_individually_curated_valid_geometry(self):
        catalog = themes._catalog()["themes"]
        self.assertEqual(len(catalog), 25)
        geometries = set()
        for theme in catalog:
            with self.subTest(theme=theme["id"]):
                self.assertTrue(scenes.valid_layout(theme["desktopLayout"]))
                from PIL import Image
                with Image.open(themes.ROOT / theme["wallpaper"]) as image:
                    self.assertEqual(theme["sourceSize"], list(image.size))
                geometries.add(json.dumps(theme["desktopLayout"]["anchors"], sort_keys=True))
        self.assertEqual(len(geometries), 3)

    def test_scene_uses_image_identity_so_accent_and_title_edits_do_not_move_widgets(self):
        original = scenes.scene_for_theme(self.theme)
        variant = copy.deepcopy(self.theme)
        variant.update(id="torii-dawn-custom", name="Different name")
        variant["colors"]["accentBlue"] = "#123456"
        self.assertEqual(scenes.scene_for_theme(variant), original)
        original["layout"]["anchors"]["clock"][0] = 0.99
        self.assertNotEqual(original["layout"], self.theme["desktopLayout"])

    def test_old_custom_manifest_inherits_metadata_by_wallpaper_hash(self):
        variant = copy.deepcopy(self.theme)
        variant.update(id="torii-dawn-custom", custom={"baseThemeId": "torii-dawn"})
        for key in ("sourceSize", "desktopLayout", "imageKey"):
            variant.pop(key)
        manifest = self.state / "themes/torii-dawn-custom.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps(variant))
        with patch("PIL.Image.open", side_effect=AssertionError("Bundled geometry must not decode images")):
            restored = themes.get_theme("torii-dawn-custom")
        self.assertEqual(restored["desktopLayout"], self.theme["desktopLayout"])
        self.assertEqual(restored["sourceSize"], self.theme["sourceSize"])
        self.assertEqual(restored["imageKey"], self.theme["imageKey"])

    def test_unknown_wallpaper_uses_compact_fallback_and_only_reads_header(self):
        from PIL import Image
        wallpaper = self.base / "unknown.png"
        Image.new("RGB", (640, 400), "#123456").save(wallpaper)
        value = scenes.scene_for_theme({"wallpaper": str(wallpaper), "desktopLayout": {"mode": []}})
        self.assertEqual(value["sourceSize"], [640, 400])
        self.assertEqual(value["imageKey"], hashlib.sha256(wallpaper.read_bytes()).hexdigest())
        self.assertEqual(value["layout"], scenes.DEFAULT_LAYOUT)

    def test_malformed_layouts_are_rejected_without_exceptions(self):
        for value in (None, [], {"mode": []}, {"mode": "left", "compact": True, "anchors": {}},
                      {**scenes.DEFAULT_LAYOUT, "anchors": {**scenes.DEFAULT_LAYOUT["anchors"], "clock": [float("nan"), 0]}},
                      {**scenes.DEFAULT_LAYOUT, "anchors": {**scenes.DEFAULT_LAYOUT["anchors"], "clock": [True, 0]}}):
            with self.subTest(value=value):
                self.assertFalse(scenes.valid_layout(value))

    def test_oversized_dimensions_fall_back_to_curated_geometry_or_image_header(self):
        value = copy.deepcopy(self.theme)
        value["sourceSize"] = [10 ** 400, 1]
        inherited = scenes.scene_for_theme(value, curated=themes._catalog()["themes"])
        from_header = scenes.scene_for_theme(value)
        self.assertEqual(inherited["sourceSize"], self.theme["sourceSize"])
        self.assertEqual(from_header["sourceSize"], self.theme["sourceSize"])

    def test_runtime_theme_exports_geometry_but_does_not_commit_scene(self):
        files, _ = themes.render_theme(self.theme, home=self.home, state_dir=self.state)
        runtime = json.loads(files[self.state / "theme.json"])
        self.assertEqual(runtime["imageKey"], self.theme["imageKey"])
        self.assertEqual(runtime["sourceSize"], self.theme["sourceSize"])
        self.assertEqual(runtime["desktopLayout"], self.theme["desktopLayout"])
        self.assertNotIn(self.state / "scene.json", files)

    def test_scene_is_published_only_after_wallpaper_is_accepted(self):
        previous = {"version": 1, "imageKey": "previous"}
        profiles._json(self.state / "scene.json", previous)
        observed = []
        def run(command, **kwargs):
            observed.append(command)
            self.assertEqual(profiles._load(self.state / "scene.json"), previous)
            return subprocess.CompletedProcess(command, 0, "", "")
        report = {"theme": self.theme, "wallpaper": self.theme["wallpaper"]}
        with patch.object(profiles, "_run", side_effect=run), patch.object(profiles, "_apply_desktop_preferences"):
            profiles._apply_theme_effects(report, state_dir=self.state)
        self.assertEqual(observed[0][:2], ["awww", "img"])
        self.assertEqual(profiles._load(self.state / "scene.json"), scenes.scene_for_theme(self.theme))

    def test_failed_wallpaper_and_dry_run_never_publish_scene(self):
        previous = {"version": 1, "imageKey": "previous"}
        profiles._json(self.state / "scene.json", previous)
        report = {"theme": self.theme, "wallpaper": self.theme["wallpaper"]}
        with patch.object(profiles, "_run", side_effect=profiles.ProfileError("wallpaper failed")), patch.object(profiles, "_apply_desktop_preferences"):
            with self.assertRaisesRegex(profiles.ProfileError, "wallpaper failed"):
                profiles._apply_theme_effects(report, state_dir=self.state)
        with patch.object(profiles, "_run"), patch.object(profiles, "_apply_desktop_preferences"):
            profiles._apply_theme_effects(report, state_dir=self.state, dry_run=True)
        self.assertEqual(profiles._load(self.state / "scene.json"), previous)

    def test_unchanged_image_does_not_rewrite_scene(self):
        profiles._json(self.state / "scene.json", scenes.scene_for_theme(self.theme))
        with patch.object(profiles, "_run"), patch.object(profiles, "_apply_desktop_preferences"), patch.object(profiles, "_json") as write:
            profiles._apply_theme_effects({"theme": self.theme, "wallpaper": self.theme["wallpaper"]}, state_dir=self.state)
        write.assert_not_called()

    def test_successful_wallpaper_replaces_malformed_scene_document(self):
        self.state.mkdir(parents=True)
        (self.state / "scene.json").write_text("{unfinished")
        with patch.object(profiles, "_run"), patch.object(profiles, "_apply_desktop_preferences"):
            profiles._apply_theme_effects({"theme": self.theme, "wallpaper": self.theme["wallpaper"]}, state_dir=self.state)
        self.assertEqual(profiles._load(self.state / "scene.json"), scenes.scene_for_theme(self.theme))

    def test_snapshot_treats_malformed_derived_state_as_absent_for_recovery(self):
        self.state.mkdir(parents=True)
        (self.state / "scene.json").write_text("{unfinished")
        (self.state / "motion.json").write_text("{unfinished")
        profiles._json(self.state / "theme.json", self.theme)
        snapshot = self.base / "snapshot"
        profiles._record_runtime(self.state, snapshot)
        runtime = profiles._load(snapshot / "runtime.json")
        self.assertIsNone(runtime["scene.json"])
        self.assertIsNone(runtime["motion.json"])
        self.assertEqual(runtime["theme.json"], self.theme)
        profiles._restore_runtime(self.state, snapshot)
        self.assertEqual(profiles._load(self.state / "scene.json"), scenes.scene_for_theme(self.theme))
        self.assertFalse((self.state / "motion.json").exists())

    def test_adaptive_battery_transition_is_short_and_expressive_override_is_preserved(self):
        profiles._json(self.state / "motion.json", {"mode": "battery"})
        report = {"wallpaper": self.theme["wallpaper"]}
        for settings, duration, fps in (({}, "0.18", "30"), ({"fullMotion": True}, "0.65", "60")):
            profiles._json(self.state / "settings.json", settings)
            with patch.object(profiles, "_run") as run, patch.object(profiles, "_apply_desktop_preferences"):
                profiles._apply_theme_effects(report, state_dir=self.state)
            command = run.call_args.args[0]
            self.assertEqual(command[command.index("--transition-duration") + 1], duration)
            self.assertEqual(command[command.index("--transition-fps") + 1], fps)

    def test_malformed_or_nonobject_motion_state_uses_normal_transition(self):
        self.state.mkdir(parents=True)
        for payload in ("null", "[]", '"battery"', "true", "{unfinished"):
            with self.subTest(payload=payload):
                (self.state / "motion.json").write_text(payload)
                with patch.object(profiles, "_run") as run, patch.object(profiles, "_apply_desktop_preferences"):
                    profiles._apply_theme_effects({"wallpaper": self.theme["wallpaper"]}, state_dir=self.state)
                command = run.call_args.args[0]
                self.assertEqual(command[command.index("--transition-duration") + 1], "0.65")

    def test_runtime_snapshot_restores_scene_and_removes_initially_absent_scene(self):
        snapshot = self.base / "snapshot"
        profiles._record_runtime(self.state, snapshot)
        profiles._json(self.state / "scene.json", scenes.scene_for_theme(self.theme))
        profiles._restore_runtime(self.state, snapshot)
        self.assertFalse((self.state / "scene.json").exists())
        old = {"version": 1, "imageKey": "previous"}
        profiles._json(self.state / "scene.json", old)
        profiles._record_runtime(self.state, snapshot)
        profiles._json(self.state / "scene.json", scenes.scene_for_theme(self.theme))
        profiles._restore_runtime(self.state, snapshot)
        self.assertEqual(profiles._load(self.state / "scene.json"), old)

    def test_legacy_or_initially_missing_scene_is_reconstructed_and_published_last(self):
        snapshot = self.base / "snapshot"
        previous = {"id": self.theme["id"], "wallpaper": self.theme["wallpaper"], "colors": self.theme["colors"]}
        real_json = profiles._json
        for include_null in (False, True):
            with self.subTest(include_null=include_null):
                runtime = {"theme.json": previous, "motion.json": {"mode": "normal"}, "settings.json": {"dnd": True}}
                if include_null:
                    runtime["scene.json"] = None
                real_json(snapshot / "runtime.json", runtime)
                real_json(self.state / "scene.json", {"version": 1, "imageKey": "new-scene"})
                written = []
                def write(path, value):
                    written.append(path.name)
                    real_json(path, value)
                with patch.object(profiles, "_json", side_effect=write):
                    profiles._restore_runtime(self.state, snapshot)
                self.assertEqual(written[-1], "scene.json")
                self.assertEqual(profiles._load(self.state / "theme.json"), previous)
                self.assertEqual(profiles._load(self.state / "scene.json"), scenes.scene_for_theme(self.theme))

    def test_legacy_snapshot_without_wallpaper_removes_stale_scene(self):
        snapshot = self.base / "snapshot"
        profiles._json(snapshot / "runtime.json", {"theme.json": {"id": "legacy"}})
        profiles._json(self.state / "scene.json", scenes.scene_for_theme(self.theme))
        profiles._restore_runtime(self.state, snapshot)
        self.assertFalse((self.state / "scene.json").exists())

    def test_scene_write_failure_rolls_back_live_theme_transaction(self):
        previous = {"version": 1, "imageKey": "previous"}
        profiles._json(self.state / "scene.json", previous)
        profiles._json(self.state / "theme.json", {"id": "before"})
        real_json = profiles._json
        failed = False
        def write(path, value):
            nonlocal failed
            if path.name == "scene.json" and not failed:
                failed = True
                raise OSError("scene commit failed")
            real_json(path, value)
        def apply(*args, **kwargs):
            real_json(self.state / "theme.json", {"id": "after"})
            return {"theme": self.theme, "wallpaper": self.theme["wallpaper"]}
        with patch.object(profiles, "_assert_unlocked"), patch.object(profiles, "ensure_original"), \
                patch.object(profiles, "_capture_desktop_state"), patch.object(profiles, "_refresh_desktop"), \
                patch.object(profiles, "_restore_desktop_state"), patch.object(profiles, "_apply_desktop_preferences"), \
                patch.object(profiles, "_run"), patch.object(profiles, "_json", side_effect=write), \
                patch.object(themes, "apply_theme", side_effect=apply):
            with self.assertRaisesRegex(profiles.ProfileError, "previous files and wallpaper restored"):
                profiles.apply_theme_live("torii-dawn", home=self.home, state_dir=self.state)
        self.assertTrue(failed)
        self.assertEqual(profiles._load(self.state / "theme.json"), {"id": "before"})
        self.assertEqual(profiles._load(self.state / "scene.json"), previous)
        self.assertFalse((self.state / "transaction.json").exists())

    def test_failed_first_scene_commit_reconstructs_previous_wallpaper_scene(self):
        previous = {"id": self.theme["id"], "wallpaper": self.theme["wallpaper"], "colors": self.theme["colors"]}
        profiles._json(self.state / "theme.json", previous)
        self.assertFalse((self.state / "scene.json").exists())
        next_theme = themes.get_theme("sunset-shrine")
        real_json = profiles._json
        failed = False
        def write(path, value):
            nonlocal failed
            real_json(path, value)
            if path.name == "scene.json" and not failed:
                failed = True
                raise OSError("scene fsync failed after replace")
        def apply(*args, **kwargs):
            real_json(self.state / "theme.json", next_theme)
            return {"theme": next_theme, "wallpaper": next_theme["wallpaper"]}
        with patch.object(profiles, "_assert_unlocked"), patch.object(profiles, "ensure_original"), \
                patch.object(profiles, "_capture_desktop_state"), patch.object(profiles, "_refresh_desktop"), \
                patch.object(profiles, "_restore_desktop_state"), patch.object(profiles, "_apply_desktop_preferences"), \
                patch.object(profiles, "_run"), patch.object(profiles, "_json", side_effect=write), \
                patch.object(themes, "apply_theme", side_effect=apply):
            with self.assertRaisesRegex(profiles.ProfileError, "previous files and wallpaper restored"):
                profiles.apply_theme_live("sunset-shrine", home=self.home, state_dir=self.state)
        self.assertTrue(failed)
        self.assertEqual(profiles._load(self.state / "theme.json"), previous)
        self.assertEqual(profiles._load(self.state / "scene.json"), scenes.scene_for_theme(self.theme))
        self.assertFalse((self.state / "transaction.json").exists())

    def test_interrupted_theme_recovery_restores_committed_scene(self):
        previous = {"version": 1, "imageKey": "previous"}
        profiles._json(self.state / "scene.json", previous)
        snapshot = self.state / "theme-transactions/interrupted"
        profiles.capture_snapshot(self.home, snapshot)
        profiles._record_runtime(self.state, snapshot)
        profiles._record_variants(self.state, snapshot)
        profiles._json(self.state / "transaction.json", {
            "kind": "theme", "snapshot": str(snapshot),
            "previous_state": {"profile": "sumi", "installed": True},
        })
        profiles._json(self.state / "scene.json", scenes.scene_for_theme(self.theme))
        with patch.object(profiles, "_assert_unlocked"), patch.object(profiles, "_install_profile_switch"), \
                patch.object(profiles, "_refresh_desktop"), patch.object(profiles, "_restore_desktop_state"):
            profiles.restore_pending(home=self.home, state_dir=self.state)
        self.assertEqual(profiles._load(self.state / "scene.json"), previous)
        self.assertFalse((self.state / "transaction.json").exists())


if __name__ == "__main__":
    unittest.main()
