import json
import os
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import patch

from sumi import themes


class ThemeLibraryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {"SUMI_STATE_DIR": str(Path(self.directory.name) / "state"), "SUMI_DATA_DIR": str(Path(self.directory.name) / "data")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    def test_legacy_assignments_are_data_and_commands_are_rejected(self):
        values = themes.parse_assignments('NAME="A quiet evening"\nEMPTY=\nTEXT_MAIN="#efece8"\n')
        self.assertEqual(values["NAME"], "A quiet evening")
        self.assertEqual(values["EMPTY"], "")
        for source in ('NAME="$(touch /tmp/no)"', 'NAME=`whoami`', 'NAME=quiet;id', 'source /etc/profile', 'NAME=a b'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                themes.parse_assignments(source)

    def test_catalog_has_all_wallpapers_and_preserves_legacy_mappings(self):
        catalog = themes.list_themes()
        self.assertEqual(len(catalog), 25)
        self.assertEqual(themes._catalog()["default"], "sumi-ember")
        expected = {}  # Palette presets use the three original, licensed backdrops.
        for theme in catalog:
            self.assertTrue(Path(theme["wallpaper"]).is_file())
            self.assertTrue(Path(theme["thumbnail"]).is_file())
            self.assertEqual(set(theme["colors"]), set(themes.COLOR_KEYS))
            self.assertGreaterEqual(themes.contrast(theme["colors"]["textMain"], theme["colors"]["bgPanelStrong"]), 7)
            self.assertGreaterEqual(themes.contrast(theme["colors"]["textSoft"], theme["colors"]["bgPanelStrong"]), 4.5)
            if theme["id"] in expected:
                self.assertEqual(Path(theme["wallpaper"]).name, expected[theme["id"]])

    def test_color_formats_have_correct_qt_alpha_order(self):
        self.assertEqual(themes.color("rgba(14,22,30,0.66)"), "#a80e161e")
        self.assertEqual(themes.color("rgba(d7ecffee)"), "#eed7ecff")
        self.assertEqual(themes.color("rgba(243,223,183ee)"), "#eef3dfb7")
        self.assertEqual(themes.hypr_color("#eed7ecff"), "rgba(d7ecffee)")
        self.assertEqual(themes.opaque("#eed7ecff"), "#d7ecff")

    def test_return_values_cannot_mutate_catalog(self):
        theme = themes.get_theme("sunset-shrine")
        theme["colors"]["textMain"] = "#000000"
        self.assertNotEqual(themes.get_theme("sunset-shrine")["colors"]["textMain"], "#000000")

    def test_jsonc_merge_preserves_comments_strings_and_unrelated_colors(self):
        original = '''{\n  // keep my editor preferences\n  "token": "literal // comment /* and ,} */",\n  "editor.fontSize": 13,\n  "workbench.colorCustomizations": {\n    /* custom ruler */\n    "editorRuler.foreground": "#123456",\n    "editor.background": "#000000",\n  },\n}\n'''
        modified = themes.merge_jsonc(original, {"workbench.colorCustomizations": {
            "editor.background": "#111420", "editor.foreground": "#f2ede4",
        }})
        self.assertIn("// keep my editor preferences", modified)
        self.assertIn("/* custom ruler */", modified)
        self.assertIn('"token": "literal // comment /* and ,} */"', modified)
        self.assertIn('"editor.fontSize": 13', modified)
        self.assertIn('"editorRuler.foreground": "#123456"', modified)
        parsed = json.loads(themes._jsonc_clean(modified))
        self.assertEqual(parsed["workbench.colorCustomizations"]["editor.background"], "#111420")
        self.assertEqual(parsed["workbench.colorCustomizations"]["editor.foreground"], "#f2ede4")
        self.assertEqual(themes.merge_jsonc(modified, {"workbench.colorCustomizations": {
            "editor.background": "#111420", "editor.foreground": "#f2ede4",
        }}), modified)

    def test_wallpaper_import_keeps_original_and_generates_readable_palette(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "assets/themes/catalog.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text('{"version":1,"default":"sunset-shrine","themes":[]}')
            catalog_before = catalog.read_bytes()
            source = root / "My New Wallpaper.png"
            Image.new("RGB", (320, 180), "#3689a0").save(source)
            original = source.read_bytes()
            with patch.object(themes, "ROOT", root), patch.object(themes, "CATALOG", catalog):
                theme = themes.import_wallpaper(source)
                self.assertEqual(theme["id"], "my-new-wallpaper")
                self.assertEqual(Path(theme["wallpaper"]).read_bytes(), original)
                self.assertEqual(source.read_bytes(), original)
                self.assertEqual(themes.import_wallpaper(source)["id"], theme["id"])
                self.assertEqual(len(themes.list_themes()), 1)
                self.assertGreaterEqual(themes.contrast(theme["colors"]["textMain"], theme["colors"]["bgPanelStrong"]), 7)
                self.assertTrue(Path(theme['wallpaper']).is_relative_to(Path(os.environ['SUMI_DATA_DIR'])))
                self.assertEqual(catalog.read_bytes(), catalog_before)
                self.assertEqual(list(root.glob('assets/wallpapers/*')), [])

    def test_import_failure_leaves_no_partial_library_entry(self):
        from PIL import Image
        source = Path(self.directory.name) / 'example.png'
        Image.new('RGB', (20, 20), '#ff0000').save(source)
        real_write = themes._atomic_write
        def fail_manifest(path, content, *args):
            if path.name == 'theme.json':
                raise OSError('manifest write failed')
            return real_write(path, content, *args)
        before = themes.CATALOG.read_bytes()
        with patch.object(themes, '_atomic_write', side_effect=fail_manifest):
            with self.assertRaisesRegex(OSError, 'manifest write failed'):
                themes.import_wallpaper(source)
        self.assertEqual(themes.CATALOG.read_bytes(), before)
        self.assertEqual(len(themes.list_themes()), 25)
        self.assertEqual(list((Path(os.environ['SUMI_DATA_DIR']) / 'themes/imported').iterdir()), [])

    def test_invalid_private_manifest_does_not_hide_bundled_library(self):
        manifest = Path(os.environ['SUMI_DATA_DIR']) / 'themes/imported/broken/theme.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text('[]')
        self.assertEqual(len(themes.list_themes()), 25)

    def test_parallel_same_name_imports_preserve_both_and_deduplicate_content(self):
        from PIL import Image
        sources = []
        for number, color in enumerate(('#ff0000', '#0000ff')):
            source = Path(self.directory.name) / str(number) / 'same-name.png'
            source.parent.mkdir()
            Image.new('RGB', (20, 20), color).save(source)
            sources.append(source)
        barrier = threading.Barrier(2)
        def import_at_once(source):
            barrier.wait(timeout=5)
            return themes.import_wallpaper(source)
        before = themes.CATALOG.read_bytes()
        with ThreadPoolExecutor(max_workers=2) as executor:
            imported = list(executor.map(import_at_once, sources))
        self.assertEqual(len({item['id'] for item in imported}), 2)
        self.assertEqual(len(themes.list_themes()), 27)
        for source, item in zip(sources, imported):
            self.assertEqual(Path(item['wallpaper']).read_bytes(), source.read_bytes())
        with ThreadPoolExecutor(max_workers=2) as executor:
            duplicate = list(executor.map(import_at_once, [sources[0], sources[0]]))
        self.assertEqual({item['id'] for item in duplicate}, {imported[0]['id']})
        self.assertEqual(len(themes.list_themes()), 27)
        self.assertEqual(themes.CATALOG.read_bytes(), before)

    def test_imported_theme_can_be_applied_without_a_writable_source_tree(self):
        from PIL import Image
        source = Path(self.directory.name) / 'personal.png'
        Image.new('RGB', (20, 20), '#246824').save(source)
        imported = themes.import_wallpaper(source)
        target_home = Path(self.directory.name) / 'home'
        target_state = Path(os.environ['SUMI_STATE_DIR'])
        report = themes.apply_theme(imported['id'], home=target_home, state_dir=target_state)
        self.assertEqual(report['theme']['id'], imported['id'])
        self.assertEqual(json.loads((target_state / 'theme.json').read_text())['id'], imported['id'])


class ThemeTransactionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name) / "home"
        self.home.mkdir()
        self.state = self.home / ".local/state/sumi"

    def tearDown(self):
        self.directory.cleanup()

    def put(self, path, content):
        target = self.home / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return target

    def test_dry_run_writes_nothing_and_lists_targets(self):
        report = themes.apply_theme("sunset-shrine", home=self.home, state_dir=self.state, dry_run=True)
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertTrue(all(item["status"] == "planned" for item in report["changed"]))
        self.assertIn(["hyprctl", "reload"], report["reload_commands"])

    def test_application_settings_and_authentication_are_preserved(self):
        kitty = self.put(".config/kitty/kitty.conf", "font_size 11.5\nbackground_opacity 0.7\nmap ctrl+a new_tab\n")
        ghostty = self.put(".config/ghostty/config.ghostty", "# user's font tuning\nfont-size = 11\nkeybind = ctrl+a=new_tab\n")
        gtk = self.put(".config/gtk-3.0/settings.ini", "# user's GTK settings\n[Settings]\ngtk-icon-theme-name=Papirus\ngtk-theme-name=Old\n[Other]\nunchanged=yes\n")
        css = self.put(".config/gtk-3.0/gtk.css", "/* user's rules */\nbutton { padding: 4px; }\n")
        qt = self.put(".config/qt6ct/qt6ct.conf", "[Appearance]\nstyle=kvantum\n[Fonts]\ngeneral=My Font\n")
        hypr = self.put(".config/hypr/config/theme.lua", 'local M = {}\nM.terminal = "kitty"\nreturn M\n')
        general = "general {\n    hide_cursor = true\n    auth {\n        pam_module = custom-policy\n    }\n}\n"
        lock = self.put(".config/hypr/hyprlock.conf", general + "\nbackground {\n    path = screenshot\n}\ninput-field {\n    placeholder_text = Type to unlock\n    fail_text = $PAMFAIL\n}\n")
        report = themes.apply_theme("sunset-shrine", home=self.home, state_dir=self.state)
        self.assertIn("font_size 11.5", kitty.read_text())
        self.assertIn("background_opacity 0.7", kitty.read_text())
        self.assertIn("map ctrl+a new_tab", kitty.read_text())
        self.assertIn("auto_reload_config 0.1", kitty.read_text())
        self.assertIn("include " + str(self.home / ".config/sumi/generated/kitty.conf"), kitty.read_text())
        self.assertIn("color15 ", (self.home / ".config/sumi/generated/kitty.conf").read_text())
        self.assertIn("keybind = ctrl+a=new_tab", ghostty.read_text())
        self.assertIn("gtk-icon-theme-name=Papirus", gtk.read_text())
        self.assertIn("[Other]\nunchanged=yes", gtk.read_text())
        self.assertNotIn("button { padding: 4px; }", css.read_text())
        self.assertEqual(css.read_text().count("@import"), 1)
        self.assertIn("style=kvantum", qt.read_text())
        self.assertIn("general=My Font", qt.read_text())
        self.assertIn('M.terminal = "kitty"', hypr.read_text())
        self.assertIn("general {\n    hide_cursor = true\n}\n", lock.read_text())
        self.assertIn("auth {\n    pam {\n        module = custom-policy\n    }\n}\n", lock.read_text())
        self.assertNotIn("pam_module", lock.read_text())
        self.assertIn("placeholder_text = Type to unlock", lock.read_text())
        self.assertIn("fail_text = $PAMFAIL", lock.read_text())
        runtime = json.loads((self.state / "theme.json").read_text())
        self.assertEqual(runtime["id"], "sunset-shrine")
        self.assertEqual(runtime["font"], "Adwaita Sans")
        self.assertNotIn("terminal", runtime)
        self.assertTrue(any(item["path"].endswith("theme.json") for item in report["changed"]))
        again = themes.apply_theme("sunset-shrine", home=self.home, state_dir=self.state)
        self.assertTrue(all(item["status"] == "unchanged" for item in again["changed"]))

    def test_sumi_gtk_stylesheet_takes_over_legacy_colors_without_editing_external_css(self):
        gtk = self.put(".config/gtk-3.0/gtk.css", '@define-color accent_color #bac3ff;\n@import "thunar.css";\n')
        external_css = self.put(".config/gtk-3.0/thunar.css", '.thunar .view:selected { color: #bac3ff; }\n')
        original_external = external_css.read_bytes()
        themes.apply_theme("sunset-shrine", home=self.home, state_dir=self.state)
        self.assertNotIn("#bac3ff", gtk.read_text())
        self.assertNotIn("thunar.css", gtk.read_text())
        self.assertEqual(external_css.read_bytes(), original_external)
        generated = (self.home / ".config/sumi/generated/gtk3.css").read_text()
        self.assertIn("@define-color accent_color #a7bce8;", generated)
        self.assertIn("@define-color window_bg_color #1b1d2b;", generated)
        self.assertIn(".thunar .view:selected", generated)
        self.assertNotIn("opacity: 0", generated)
        self.assertNotIn("animation:", generated)

    def test_gtk_selection_contrast_handles_dark_and_light_custom_accents(self):
        for accent in ("#111111", "#dddddd", "#58749a"):
            palette = dict(themes.get_theme("sunset-shrine")["colors"], accentBlue=accent)
            css = themes._gtk_css(palette)
            selected = next(line.split()[-1].rstrip(";") for line in css.splitlines() if line.startswith("@define-color accent_fg_color "))
            self.assertGreaterEqual(themes.contrast(selected, accent), 4.5)

    def test_legacy_hyprlock_auth_migrates_exact_module_and_preserves_general_keys(self):
        original = '''general {
    hide_cursor = true
    immediate_render = true
    ignore_empty_input = false
    auth {
        # personal authentication policy
        pam_module = my-custom-policy
    }
    fractional_scaling = 2
}
'''
        normalized = themes._normalize_hyprlock_auth(original)
        self.assertNotIn("pam_module", normalized)
        self.assertIn("        module = my-custom-policy\n", normalized)
        for setting in ("    hide_cursor = true\n", "    immediate_render = true\n", "    ignore_empty_input = false\n", "    fractional_scaling = 2\n"):
            self.assertIn(setting, normalized)
        self.assertEqual(themes._normalize_hyprlock_auth(normalized), normalized)

    def test_valid_modern_hyprlock_auth_remains_unchanged(self):
        original = '''general {
    hide_cursor = true
}
auth {
    pam {
        module = my-supported-policy
        enabled = true
    }
    fingerprint {
        enabled = true
    }
}
'''
        self.assertEqual(themes._normalize_hyprlock_auth(original), original)

    def test_unknown_legacy_auth_block_is_not_reinterpreted(self):
        original = 'general {\n    auth {\n        pam_module = personal\n        unknown_setting = true\n    }\n}\n'
        self.assertEqual(themes._normalize_hyprlock_auth(original), original)

    def test_existing_editor_settings_and_neovim_receive_managed_colors(self):
        settings = self.put(".config/Antigravity IDE/User/settings.json", '{\n// keep\n"editor.fontSize": 14,\n"workbench.colorCustomizations": {"editorRuler.foreground":"#555555"},\n}\n')
        nvim = self.put(".config/nvim/init.lua", '-- personal config\nvim.o.number = true\n')
        themes.apply_theme("sunset-shrine", home=self.home, state_dir=self.state)
        parsed = json.loads(themes._jsonc_clean(settings.read_text()))
        self.assertEqual(parsed["editor.fontSize"], 14)
        self.assertEqual(parsed["workbench.colorCustomizations"]["editorRuler.foreground"], "#555555")
        self.assertEqual(parsed["workbench.colorCustomizations"]["editor.background"], "#111420")
        self.assertIn("// keep", settings.read_text())
        self.assertIn("vim.o.number = true", nvim.read_text())
        self.assertIn("SumiColors", nvim.read_text())
        again = themes.apply_theme("sunset-shrine", home=self.home, state_dir=self.state)
        self.assertTrue(all(item["status"] == "unchanged" for item in again["changed"]))

    def test_unsupported_editor_settings_are_preserved_with_warning(self):
        original = '{"workbench.colorCustomizations": null}\n'
        settings = self.put(".config/Code/User/settings.json", original)
        report = themes.apply_theme("sunset-shrine", home=self.home, state_dir=self.state)
        self.assertEqual(settings.read_text(), original)
        self.assertTrue(any("unsupported JSONC" in warning for warning in report["warnings"]))

    def test_failed_write_rolls_back_bytes_permissions_and_created_files(self):
        original = self.put(".config/ghostty/config.ghostty", "font-size = 11\n")
        original.chmod(0o640)
        before = original.read_bytes()
        write = themes._atomic_write
        counter = 0

        def fail_once(path, content, mode=0o600):
            nonlocal counter
            counter += 1
            if counter == 4:
                raise OSError("simulated full filesystem")
            return write(path, content, mode)

        with patch.object(themes, "_atomic_write", fail_once), self.assertRaisesRegex(OSError, "simulated"):
            themes.apply_theme("moonlit-fuji", home=self.home, state_dir=self.state)
        self.assertEqual(original.read_bytes(), before)
        self.assertEqual(original.stat().st_mode & 0o777, 0o640)
        self.assertFalse((self.state / "theme.json").exists())
        self.assertFalse((self.home / ".config/sumi/generated/ghostty.conf").exists())

    def test_external_symlink_is_rejected_before_any_write(self):
        outside = Path(self.directory.name) / "outside"
        outside.write_text("private config\n")
        target = self.home / ".config/ghostty/config.ghostty"
        target.parent.mkdir(parents=True)
        target.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "outside"):
            themes.apply_theme("sunset-shrine", home=self.home, state_dir=self.state)
        self.assertEqual(outside.read_text(), "private config\n")
        self.assertFalse((self.home / ".config/sumi").exists())

    def test_existing_in_home_config_symlink_survives(self):
        actual = self.put("dotfiles/ghostty.conf", "font-size = 11\n")
        target = self.home / ".config/ghostty/config.ghostty"
        target.parent.mkdir(parents=True)
        target.symlink_to(actual)
        themes.apply_theme("sunset-shrine", home=self.home, state_dir=self.state)
        self.assertTrue(target.is_symlink())
        self.assertIn("config-file = ", actual.read_text())

    def test_bad_markers_abort_before_writes(self):
        self.put(".config/ghostty/config.ghostty", themes.BEGIN + "\npartial edit\n")
        with self.assertRaisesRegex(ValueError, "markers"):
            themes.apply_theme("sunset-shrine", home=self.home, state_dir=self.state)
        self.assertFalse((self.home / ".config/sumi").exists())

    def test_custom_accent_is_saved_without_changing_base(self):
        base = themes.get_theme("sunset-shrine")
        report = themes.apply_custom_accent("sunset-shrine", "#B4CDA1", home=self.home, state_dir=self.state)
        self.assertEqual(report["theme"]["id"], "sunset-shrine-custom")
        restored = themes.get_theme("sunset-shrine-custom", state_dir=self.state)
        self.assertEqual(restored["colors"]["accentBlue"], "#b4cda1")
        self.assertEqual(themes.get_theme("sunset-shrine")["colors"], base["colors"])
        themes.apply_custom_accent("sunset-shrine-custom", "#99bbcc", home=self.home, state_dir=self.state)
        variants = [t for t in themes.list_themes(state_dir=self.state) if "custom" in t]
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0]["colors"]["accentBlue"], "#99bbcc")

    def test_custom_accent_validation_and_dry_run_do_not_write(self):
        with self.assertRaisesRegex(ValueError, "RRGGBB"):
            themes.apply_custom_accent("sunset-shrine", "red;touch /tmp/oops", home=self.home, state_dir=self.state)
        themes.apply_custom_accent("sunset-shrine", "#99bbcc", home=self.home, state_dir=self.state, dry_run=True)
        self.assertEqual(list(self.home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
