"""Screenshot boundary regressions with synthetic selector and clipboard only."""
import base64
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from sumi.actions import capture


PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2CYsAAAAASUVORK5CYII=')


class ScreenshotCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumi screenshot % fixture ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        binaries = self.root / 'bin'
        binaries.mkdir()
        (self.root / 'image.png').write_bytes(PNG)
        programs = {
            # Model the installed Hyprshot's background capture and foreground
            # cleanup exit. The child retains stdout until capture completes.
            'hyprshot': '''import os, subprocess, sys
from pathlib import Path
root = Path(os.environ['CAPTURE_FIXTURE'])
args = sys.argv[1:]
if '--raw' in args:
    code = "import os,sys,time; from pathlib import Path; time.sleep(.12); sys.stdout.buffer.write((Path(os.environ['CAPTURE_FIXTURE'])/'image.png').read_bytes())"
else:
    output = Path(args[args.index('-o') + 1]) / 'old-hyprshot.png'
    code = "import time; from pathlib import Path; time.sleep(.12); Path(" + repr(str(output)) + ").write_bytes(b'completed')"
subprocess.Popen([sys.executable, '-c', code])
raise SystemExit(1)
''',
            'systemd-run': '''import json, os, signal, subprocess, sys
from pathlib import Path
root = Path(os.environ['CAPTURE_FIXTURE'])
args = sys.argv[1:]
(root / 'unit.json').write_text(json.dumps(args))
command = args[args.index('--') + 1:]
source = next((arg.split('file:', 1)[1] for arg in args if arg.startswith('--property=StandardInput=file:')), None)
stream = open(source, 'rb') if source else subprocess.DEVNULL
try:
    process = subprocess.Popen(command, stdin=stream, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    code = process.wait(timeout=5)
    # Default service cleanup terminates background capture/clipboard children.
    # A forking service instead adopts the surviving clipboard owner.
    if '--service-type=forking' not in args or code:
        try: os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError: pass
finally:
    if source: stream.close()
raise SystemExit(code if '--service-type=forking' in args else 0)
''',
            'wl-copy': '''import os, sys, time
from pathlib import Path
root = Path(os.environ['CAPTURE_FIXTURE'])
if os.environ.get('CAPTURE_COPY_FAILURE'):
    raise SystemExit(7)
data = sys.stdin.buffer.read()
(root / 'copied.png').write_bytes(data)
pid = os.fork()
if pid:
    (root / 'clipboard.pid').write_text(str(pid))
    raise SystemExit(0)
for fd in (0, 1, 2):
    os.dup2(os.open(os.devnull, os.O_RDWR), fd)
deadline = time.monotonic() + 8
while not (root / 'release').exists() and time.monotonic() < deadline:
    if (root / 'paste-request').exists():
        (root / 'pasted.png').write_bytes(data)
        (root / 'paste-request').unlink()
    time.sleep(.02)
''',
            'notify-send': 'pass\n',
        }
        for name, body in programs.items():
            executable = binaries / name
            executable.write_text(f'#!{sys.executable}\n' + body)
            executable.chmod(0o700)
        environment = patch.dict(os.environ, HOME=str(self.root), CAPTURE_FIXTURE=str(self.root), PATH=str(binaries) + os.pathsep + os.environ['PATH'])
        environment.start()
        self.addCleanup(environment.stop)
        self.addCleanup(self.stop_clipboard)

    def stop_clipboard(self):
        (self.root / 'release').touch()
        pidfile = self.root / 'clipboard.pid'
        if pidfile.exists():
            try:
                os.kill(int(pidfile.read_text()), signal.SIGTERM)
            except ProcessLookupError:
                pass

    def test_background_capture_is_saved_and_clipboard_owner_survives(self):
        controller = Path(__file__).resolve().parents[1] / 'bin/desktopctl'
        completed = subprocess.run([sys.executable, str(controller), 'action', 'capture', 'region'], capture_output=True, text=True, timeout=5)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        saved = list((self.root / 'Pictures/Screenshots').glob('*.png'))
        self.assertEqual(len(saved), 1, 'A successful screenshot action must finish saving the capture')
        self.assertEqual(saved[0].read_bytes(), PNG)
        self.assertEqual(saved[0].stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.root / 'copied.png').read_bytes(), PNG)
        self.assertEqual(result, {'file': str(saved[0]), 'saved': True, 'copied': True})
        # Request the image after the real controller has exited, proving the
        # clipboard owner still serves content rather than merely existing.
        (self.root / 'paste-request').touch()
        deadline = time.monotonic() + 2
        while not (self.root / 'pasted.png').exists() and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertEqual((self.root / 'pasted.png').read_bytes(), PNG)

    def test_clipboard_failure_keeps_saved_image_and_reports_partial_failure(self):
        with patch.dict(os.environ, CAPTURE_COPY_FAILURE='1'):
            with self.assertRaisesRegex(RuntimeError, 'saved.*clipboard'):
                capture(['region'])
        saved = list((self.root / 'Pictures/Screenshots').glob('*.png'))
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].read_bytes(), PNG)
        self.assertFalse((self.root / 'clipboard.pid').exists())

    def test_cancelled_or_truncated_capture_never_saves_or_copies(self):
        for image in (b'', PNG[:-12]):
            with self.subTest(image_length=len(image)):
                with patch('sumi.actions.subprocess.run', return_value=subprocess.CompletedProcess([], 1, image, b'')), patch('sumi.actions.spawn') as launch:
                    with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                        capture(['region'])
                launch.assert_not_called()
                self.assertEqual(list((self.root / 'Pictures/Screenshots').iterdir()), [])

    def test_failed_save_never_replaces_clipboard(self):
        with patch('sumi.actions.atomic_write', side_effect=PermissionError('Cannot save screenshot')), patch('sumi.actions.spawn') as launch:
            with self.assertRaisesRegex(PermissionError, 'Cannot save'):
                capture(['region'])
        launch.assert_not_called()
        self.assertEqual(list((self.root / 'Pictures/Screenshots').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
