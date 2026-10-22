"""Exercise the independent annotation worker with isolated real executables.

The fake selector supplies a PNG and fake systemd-run starts the actual worker.
A gated fake editor proves capture returns while editing and checks file handoff
and cleanup. Native Satty rendering/saving remains a separate acceptance check.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zlib

from sumi.actions import capture


def fixture_png() -> bytes:
    def chunk(kind, payload):
        return struct.pack("!I", len(payload)) + kind + payload + struct.pack("!I", zlib.crc32(kind + payload))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!2I5B", 1, 1, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xa8\xcd\xe4\xff")) + chunk(b"IEND", b""))


class CaptureProcessBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sumi capture boundary ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / "home with spaces"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.runtime = self.root / "runtime"
        self.runtime.mkdir(mode=0o700)
        self.annotations = self.runtime / "sumi/annotations"
        self.image = self.root / "capture.png"
        self.image.write_bytes(fixture_png())
        self.receipt = self.root / "satty-argv.json"
        self.registration = self.root / "registration.json"
        self.gate = self.root / "finish-editing"
        self.worker_log = self.root / "worker.log"
        helpers = {
            "hyprshot": """import os, sys
from pathlib import Path
sys.stdout.buffer.write(Path(os.environ['SUMI_TEST_CAPTURE']).read_bytes())
sys.exit(int(os.environ.get('SUMI_TEST_CAPTURE_EXIT', '1')))
""",
            "systemd-run": """import json, os, subprocess, sys
from pathlib import Path
root = Path(os.environ['SUMI_TEST_ROOT'])
args = sys.argv[1:]
command = args[args.index('--') + 1:]
receipt = {'argv': args, 'command': command}
if os.environ.get('SUMI_TEST_REGISTRATION_FAIL') == '1':
    (root / 'registration.json').write_text(json.dumps(receipt))
    print('Synthetic annotation registration failure', file=sys.stderr)
    sys.exit(1)
environment = dict(os.environ)
for arg in args:
    if arg.startswith('--setenv='):
        key, value = arg[len('--setenv='):].split('=', 1)
        environment[key] = value
with (root / 'worker.log').open('ab') as errors:
    process = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=errors,
                               start_new_session=True)
receipt['worker_pid'] = process.pid
pending = root / 'registration.next.json'
pending.write_text(json.dumps(receipt))
pending.replace(root / 'registration.json')
""",
            "satty": """import json, os, sys, time
from pathlib import Path
root = Path(os.environ['SUMI_TEST_ROOT'])
args = sys.argv[1:]
captured = Path(args[args.index('--filename') + 1]).read_bytes()
receipt = {'argv': args, 'pid': os.getpid(), 'input_size': len(captured)}
pending = root / 'satty-argv.next.json'
pending.write_text(json.dumps(receipt))
pending.replace(root / 'satty-argv.json')
deadline = time.monotonic() + 3
while not (root / 'finish-editing').exists():
    if time.monotonic() >= deadline:
        print('Synthetic editor gate timed out', file=sys.stderr)
        sys.exit(72)
    time.sleep(0.01)
if os.environ.get('SUMI_TEST_SATTY_EXIT'):
    sys.exit(int(os.environ['SUMI_TEST_SATTY_EXIT']))
Path(args[args.index('--output-filename') + 1]).write_bytes(captured)
""",
        }
        for name, content in helpers.items():
            path = self.bin / name
            path.write_text(f"#!{sys.executable}\n" + content)
            path.chmod(0o700)
        self.addCleanup(patch.stopall)
        self.addCleanup(self._stop_test_children)
        patch("sumi.actions.Path.home", return_value=self.home).start()
        patch.dict(os.environ, {
            "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
            "XDG_RUNTIME_DIR": str(self.runtime),
            "SUMI_HOME": str(self.home),
            "SUMI_TEST_ROOT": str(self.root),
            "SUMI_TEST_CAPTURE": str(self.image),
            "SUMI_TEST_CAPTURE_EXIT": "1",
            "SUMI_TEST_REGISTRATION_FAIL": "0",
            "SUMI_TEST_SATTY_EXIT": "",
        }).start()

    def _wait_for(self, predicate, message):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.01)
        detail = self.worker_log.read_text(errors="replace") if self.worker_log.exists() else ""
        self.fail(message + ("\n" + detail if detail else ""))

    def _owned_pids(self):
        pids = []
        for receipt, key in ((self.registration, "worker_pid"), (self.receipt, "pid")):
            try:
                pid = int(json.loads(receipt.read_text())[key])
                arguments = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
                if any(os.fsencode(self.root) in argument for argument in arguments):
                    pids.append(pid)
            except (OSError, ValueError, KeyError):
                pass
        return pids

    def _stop_test_children(self):
        # A failing assertion must not leave a gated synthetic editor behind.
        # Only PIDs in this fixture's receipts and carrying its unique temporary
        # root in argv are eligible; unrelated desktop applications are ignored.
        self.gate.touch(exist_ok=True)
        deadline = time.monotonic() + 1
        while self._owned_pids() and time.monotonic() < deadline:
            time.sleep(0.01)
        for signum in (signal.SIGTERM, signal.SIGKILL):
            for pid in self._owned_pids():
                try:
                    os.kill(pid, signum)
                except ProcessLookupError:
                    pass
            deadline = time.monotonic() + 1
            while self._owned_pids() and time.monotonic() < deadline:
                time.sleep(0.01)

    def _started_session(self, result):
        self.assertTrue(result["launched"])
        identifier = result["annotation_id"]
        self.assertRegex(identifier, r"\A[a-f0-9]{32}\Z")
        self._wait_for(self.receipt.exists, "The independent worker did not start the editor")
        registration = json.loads(self.registration.read_text())
        self.assertIn("--service-type=exec", registration["argv"])
        command = registration["command"]
        self.assertEqual(command[1:4], ["action", "annotation-session", identifier])
        self.assertEqual(command[4], result["output"])
        self.assertEqual(Path(command[0]).name, "desktopctl")
        self.assertFalse(self.gate.exists(), "Capture waited until editing finished")
        self.assertTrue(self._owned_pids(), "The editing session already exited")
        editor = json.loads(self.receipt.read_text())
        captured = self.annotations / identifier / "capture.png"
        self.assertEqual(editor["argv"][:2], ["--filename", str(captured)])
        destination = Path(result["output"])
        self.assertEqual(editor["argv"][2:], ["--output-filename", str(destination)])
        self.assertEqual(destination.parent, self.home / "Pictures/Screenshots")
        return captured, destination

    def test_cleanup_error_delivers_private_png_and_returns_while_editing(self):
        # The selector's cleanup status1 must not discard a complete PNG.
        captured, destination = self._started_session(capture(["region", "annotate"]))
        self.assertEqual(captured.read_bytes(), self.image.read_bytes())
        self.assertEqual(stat.S_IMODE(self.annotations.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(captured.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(captured.stat().st_mode), 0o600)
        self.assertFalse(destination.exists())
        self.gate.touch()
        self._wait_for(lambda: not captured.parent.exists(), "Worker did not clean its private input after editor exit")
        self.assertEqual(destination.read_bytes(), self.image.read_bytes())
        self.assertEqual(list(destination.parent.glob("*.png")), [destination])
        self.assertEqual(list(self.annotations.iterdir()), [])

    def test_cancelled_selector_never_launches_worker_or_saves_output(self):
        self.image.write_bytes(b"")
        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            capture(["window", "annotate"])
        self.assertFalse(self.registration.exists())
        self.assertFalse(self.receipt.exists())
        self.assertEqual(list(self.annotations.glob("*/capture.png")), [])
        self.assertEqual(list((self.home / "Pictures/Screenshots").glob("*.png")), [])

    def test_truncated_png_never_launches_worker(self):
        self.image.write_bytes(fixture_png()[:-12])
        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            capture(["output", "annotate"])
        self.assertFalse(self.registration.exists())
        self.assertFalse(self.receipt.exists())
        self.assertEqual(list(self.annotations.glob("*/capture.png")), [])

    def test_registration_failure_removes_private_input_without_launching_editor(self):
        with patch.dict(os.environ, SUMI_TEST_REGISTRATION_FAIL="1"):
            with self.assertRaises(subprocess.CalledProcessError):
                capture(["region", "annotate"])
        self.assertTrue(self.registration.exists())
        self.assertFalse(self.receipt.exists())
        self.assertNotIn("worker_pid", json.loads(self.registration.read_text()))
        self.assertEqual(list(self.annotations.iterdir()), [])
        self.assertEqual(list((self.home / "Pictures/Screenshots").glob("*.png")), [])

    def test_editor_failure_cleans_input_and_preserves_existing_output(self):
        with patch.dict(os.environ, SUMI_TEST_SATTY_EXIT="7"):
            captured, destination = self._started_session(capture(["output", "annotate"]))
        destination.write_bytes(b"previously saved output")
        self.gate.touch()
        self._wait_for(lambda: not captured.parent.exists(), "Failed editor did not clean its private input")
        self.assertEqual(destination.read_bytes(), b"previously saved output")
        self.assertEqual(list(self.annotations.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
