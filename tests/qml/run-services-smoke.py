#!/usr/bin/env python3
"""Exercise Sumi's service layer without claiming live desktop services."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-qml-smoke-") as temporary:
        work = Path(temporary)
        config = work / "config"
        config.mkdir()
        for folder in ("config", "services"):
            shutil.copytree(repo / "shell" / folder, config / folder)
        harness = (Path(__file__).parent / "services-smoke.qml").read_text()
        harness = harness.replace("../../shell/config", "config").replace("../../shell/services", "services")
        (config / "shell.qml").write_text(harness)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        state = work / "state"
        environment = dict(os.environ, SUMI_PREVIEW="1", SUMI_STATE_DIR=str(state), QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime))
        for fixture in ("defaults", "nested", "flat"):
            if fixture != "defaults":
                state.mkdir(exist_ok=True)
                theme = {"id": "fixture", "name": "Fixture Theme", "colors": {"textMain": "#ffffff"}}
                typography = {"font": "Test Sans", "fontMono": "Test Mono", "fontSize": 16}
                dimensions = {"windowRounding": 11, "borderWidth": 3}
                if fixture == "nested":
                    theme.update(typography=typography, dimensions=dimensions)
                else:
                    theme.update(typography)
                    theme.update(dimensions)
                (state / "theme.json").write_text(json.dumps(theme))
                (state / "settings.json").write_text(json.dumps({"barHiddenMode": True, "dnd": True}))
                environment["SUMI_TEST_FIXTURE"] = "1"
            result = subprocess.run(["qs", "-p", str(config)], env=environment, text=True, capture_output=True, timeout=15)
            output = result.stdout + result.stderr
            if result.returncode or "SUMI_SERVICES_SMOKE_OK" not in output or "TypeError:" in output or "ReferenceError:" in output:
                raise SystemExit(output)
            label = "missing-file defaults" if fixture == "defaults" else f"loaded {fixture} theme typography/dimensions and settings"
            print(f"PASS: {label}; native API bindings; notification history/actions/sanitization; preview isolation")

        harness = (Path(__file__).parent / "notification-updates-smoke.qml").read_text()
        harness = harness.replace("../../shell/config", "config").replace("../../shell/services", "services")
        (config / "shell.qml").write_text(harness)
        notification_environment = dict(environment, SUMI_STATE_DIR=str(work / "notification-state"))
        result = subprocess.run(["qs", "-p", str(config)], env=notification_environment, text=True, capture_output=True, timeout=10)
        output = result.stdout + result.stderr
        if result.returncode or "SUMI_NOTIFICATION_UPDATES_OK" not in output or "TypeError:" in output or "ReferenceError:" in output:
            raise SystemExit(output)
        print("PASS: native-style replacements and action updates; expiry restart; no duplicate callbacks; reload suppression; transient cleanup")

        harness = (Path(__file__).parent / "storage-smoke.qml").read_text().replace("../../shell/config", "config")
        (config / "shell.qml").write_text(harness)
        environment.pop("SUMI_PREVIEW")
        process = subprocess.Popen(["qs", "-p", str(config)], env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        lines = []
        watchdog = threading.Timer(10, process.kill)
        watchdog.start()
        try:
            for line in process.stdout:
                lines.append(line)
                if "SUMI_STORAGE_WRITE_INVALID" in line:
                    staged = state / "theme.next.json"
                    staged.write_text("{invalid-json")
                    staged.replace(state / "theme.json")
                if "SUMI_STORAGE_WRITE_VALID" in line:
                    staged = state / "theme.next.json"
                    staged.write_text(json.dumps({"name": "Updated Theme", "colors": {"textMain": "#eeeeee"}}))
                    staged.replace(state / "theme.json")
            process.wait(timeout=10)
        finally:
            watchdog.cancel()
            if process.poll() is None:
                process.kill()
                process.wait()
        output = "".join(lines)
        if process.returncode or "SUMI_STORAGE_SMOKE_OK" not in output:
            raise SystemExit(output)
        if not json.loads((state / "settings.json").read_text())["reducedMotion"]:
            raise SystemExit("Settings did not persist to disk")
        print("PASS: atomic theme replacement; invalid JSON retains last valid palette; settings persist to disk")


if __name__ == "__main__":
    main()
