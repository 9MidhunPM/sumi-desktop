"""Resolve real desktop entries in a private, offscreen Quickshell instance."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("qs"), "Quickshell is required for the app icon QML test")
class AppIconTests(unittest.TestCase):
    def test_desktop_classes_webapps_urls_fallback_and_event_updates(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="sumi-app-icons-") as directory:
            work = Path(directory)
            config, data = work / "config", work / "data"
            services, icons, applications = config / "services", config / "assets/icons", data / "applications"
            for path in (services, icons, applications):
                path.mkdir(parents=True)
            shutil.copyfile(repo / "shell/services/AppIcons.qml", services / "AppIcons.qml")
            shutil.copyfile(repo / "shell/assets/icons/grid.svg", icons / "grid.svg")
            (services / "qmldir").write_text("singleton AppIcons AppIcons.qml\n")
            first, second = icons / "first icon.svg", icons / "second.svg"
            for path, color in ((first, "red"), (second, "blue")):
                path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"><rect width="24" height="24" fill="{color}"/></svg>')
            app_hash = "a" * 32
            fixtures = [
                ("kitty", "Kitty Fixture", first, "Kitty", False),
                ("zen", "Zen Fixture", first, "zen", False),
                ("thunar", "Thunar Fixture", second, "Thunar", False),
                ("chromium", "Chromium Fixture", second, "Chromium", False),
                ("brave-browser", "Brave Fixture", first, "brave-browser", False),
                (f"brave-{app_hash}-Default", "Webapp Fixture", second, f"crx_{app_hash}", False),
                ("org.fixture.Hidden", "Hidden Fixture", second, "HiddenClass", True),
                ("org.fixture.Broken", "Broken Fixture", "sumi-icon-that-cannot-exist", "", False),
                ("org.fixture.Url", "URL Fixture", second.as_uri(), "", False),
            ]
            for app_id, name, icon, wmclass, hidden in fixtures:
                (applications / f"{app_id}.desktop").write_text(
                    f"[Desktop Entry]\nType=Application\nName={name}\nExec=true\nIcon={icon}\nStartupWMClass={wmclass}\nNoDisplay={'true' if hidden else 'false'}\n")
            (config / "shell.qml").write_text('''
import QtQuick
import Quickshell
import Quickshell.Io
import "services" as S

ShellRoot {
    id: root
    property string first: Quickshell.iconPath(Quickshell.env("FIRST_ICON"), true)
    property string second: Quickshell.iconPath(Quickshell.env("SECOND_ICON"), true)
    property string dynamicIcon: S.AppIcons.appIcon(window)
    property string dynamicName: S.AppIcons.displayName(window)
    property int phase: 0
    property int updateWaits: 0
    QtObject {
        id: window
        property var lastIpcObject: ({})
        property QtObject wayland: QtObject { property string appId: "" }
    }
    Image { id: appImage; source: root.first; width: 20; height: 20 }
    Image { id: fallbackImage; source: S.AppIcons.fallback; width: 20; height: 20 }
    FileView { id: desktopFile; path: Quickshell.env("KITTY_DESKTOP") }
    function assertEqual(actual, expected, label) {
        if (actual !== expected) throw new Error(label + ": " + actual + " !== " + expected);
    }
    Timer {
        interval: 40; running: true; repeat: true
        onTriggered: {
            try {
                const appHash = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
                if (root.phase === 0) {
                    if (!root.first || !root.second) throw new Error("Fixture paths did not resolve");
                    for (const input of ["kitty", "KITTY.desktop", "org.kitty_terminal.kitty", "zen-browser", "brave-webapp"])
                        root.assertEqual(S.AppIcons.appIcon(input), root.first, input);
                    for (const input of ["Thunar", "org.xfce.thunar", "Chromium", "chromium-browser", "HiddenClass"])
                        root.assertEqual(S.AppIcons.appIcon(input), root.second, input);
                    for (const input of ["brave-" + appHash + "-Default", "brave-webapp-" + appHash, "crx_" + appHash])
                        root.assertEqual(S.AppIcons.appIcon(input), root.second, input);
                    root.assertEqual(S.AppIcons.appIcon({wayland: {appId: "brave-browser"}, lastIpcObject: {"class": "crx_" + appHash}}), root.second, "StartupWMClass webapp outranks generic browser entry");
                    root.assertEqual(S.AppIcons.appIcon("org.fixture.Url"), Quickshell.env("SECOND_URL"), "Full file URL");
                    const provider = "image://icon/custom.svg?path=/tmp/fixture path";
                    root.assertEqual(S.AppIcons.iconUrl(provider), provider, "Provider URL query preserved");
                    for (const input of [null, "", {}, "sumi-unknown-application", "org.fixture.Broken"])
                        root.assertEqual(S.AppIcons.appIcon(input), S.AppIcons.fallback, "Unknown fallback");
                    root.assertEqual(root.dynamicIcon, S.AppIcons.fallback, "Initial missing class");
                    root.assertEqual(appImage.status, Image.Ready, "Actual application image loads");
                    root.assertEqual(fallbackImage.status, Image.Ready, "Bundled fallback image loads");
                    window.wayland.appId = "kitty";
                } else if (root.phase === 1) {
                    root.assertEqual(root.dynamicIcon, root.first, "Late Wayland appId updates binding");
                    root.assertEqual(root.dynamicName, "Kitty Fixture", "Desktop display name");
                    window.lastIpcObject = {"class": "brave-webapp-" + appHash};
                } else if (root.phase === 2) {
                    root.assertEqual(root.dynamicIcon, root.second, "Specific IPC webapp outranks generic appId");
                    root.assertEqual(root.dynamicName, "Webapp Fixture", "Webapp name preserved");
                    window.lastIpcObject = {};
                    desktopFile.setText("[Desktop Entry]\\nType=Application\\nName=Kitty Fixture\\nExec=true\\nIcon=" + Quickshell.env("SECOND_ICON") + "\\nStartupWMClass=Kitty\\n");
                } else {
                    if (DesktopEntries.byId("kitty").icon !== Quickshell.env("SECOND_ICON") && root.updateWaits++ < 100) return;
                    root.assertEqual(root.dynamicIcon, root.second, "Desktop icon change updates binding");
                    console.info("SUMI_APP_ICONS_OK");
                    Qt.quit();
                }
                root.phase++;
            } catch (error) {
                console.error("SUMI_APP_ICONS_FAILED", error);
                Qt.exit(1);
            }
        }
    }
}
''')
            runtime = work / "runtime"
            runtime.mkdir(mode=0o700)
            environment = dict(os.environ, SUMI_PREVIEW="1", QT_QPA_PLATFORM="offscreen", HOME=str(work),
                               XDG_RUNTIME_DIR=str(runtime), XDG_CONFIG_HOME=str(work / "xdg-config"),
                               XDG_CACHE_HOME=str(work / "cache"), XDG_DATA_HOME=str(data),
                               XDG_DATA_DIRS=str(work / "empty-data"), FIRST_ICON=str(first),
                               SECOND_ICON=str(second), SECOND_URL=second.as_uri(),
                               KITTY_DESKTOP=str(applications / "kitty.desktop"))
            result = subprocess.run(["qs", "-p", str(config), "-n"], env=environment,
                                    text=True, capture_output=True, timeout=10)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("SUMI_APP_ICONS_OK", output)
            self.assertNotIn("SUMI_APP_ICONS_FAILED", output)
            self.assertNotIn("ReferenceError", output)
            self.assertNotIn("TypeError", output)


if __name__ == "__main__":
    unittest.main()
