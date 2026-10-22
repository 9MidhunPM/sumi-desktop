import json
from io import StringIO
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from sumi import actions, annotation
from sumi.actions import search_files, clipboard, main, capture, recording


class ActionsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        (self.root / "runtime").mkdir()
        environment = patch.dict(os.environ, SUMI_STATE_DIR=str(self.root / "state"), XDG_RUNTIME_DIR=str(self.root / "runtime"))
        environment.start()
        self.addCleanup(environment.stop)

    def test_annotation_accepts_complete_png_despite_hyprshot_cleanup_failure(self):
        image = b'\x89PNG\r\n\x1a\n' + b'image data' + b'\x00\x00\x00\x00IEND\xaeB`\x82'
        with patch('sumi.actions.Path.home', return_value=self.root), patch('sumi.actions.shutil.which', return_value='/usr/bin/satty'), patch('sumi.actions.subprocess.run', return_value=subprocess.CompletedProcess([], 1, image, b'')), patch('sumi.actions.spawn') as launch:
            result = capture(['output', 'annotate'])
        arguments = launch.call_args.args[0]
        self.assertEqual(arguments[1:3], ['action', 'annotation-session'])
        self.assertTrue(Path(arguments[0]).is_absolute())
        self.assertEqual(arguments[3], result['annotation_id'])
        captured = self.root / 'runtime/sumi/annotations' / arguments[3] / 'capture.png'
        self.assertEqual(captured.read_bytes(), image)
        self.assertEqual(captured.stat().st_mode & 0o777, 0o600)
        self.assertEqual(captured.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(captured.parent.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(Path(arguments[4]).parent, self.root / 'Pictures/Screenshots')
        self.assertFalse(Path(arguments[4]).exists(), 'Only Satty Save should create the output')

    def test_annotation_rejects_cancelled_or_incomplete_capture(self):
        with patch('sumi.actions.Path.home', return_value=self.root), patch('sumi.actions.shutil.which', return_value='/usr/bin/satty'), patch('sumi.actions.subprocess.run', return_value=subprocess.CompletedProcess([], 1, b'\x89PNG\r\n\x1a\n', b'')), patch('sumi.actions.spawn') as call:
            with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                capture(['region', 'annotate'])
            call.assert_not_called()
        self.assertFalse((self.root / 'runtime/sumi/annotations').exists())

    def test_annotation_failed_registration_removes_only_private_input(self):
        output = self.root / 'saved.png'
        output.write_bytes(b'existing saved image')
        launcher = Mock(side_effect=subprocess.CalledProcessError(1, ['systemd-run']))
        with self.assertRaises(subprocess.CalledProcessError):
            annotation.launch(b'private image', output, launcher)
        self.assertEqual(list((self.root / 'runtime/sumi/annotations').iterdir()), [])
        self.assertEqual(output.read_bytes(), b'existing saved image')

    def test_annotation_worker_failure_removes_input_without_touching_output(self):
        output = self.root / 'saved.png'
        output.write_bytes(b'existing saved image')
        result = annotation.launch(b'private image', output, Mock())
        captured = self.root / 'runtime/sumi/annotations' / result['annotation_id'] / 'capture.png'
        with patch('sumi.annotation.subprocess.Popen', side_effect=FileNotFoundError('missing editor')):
            with self.assertRaises(FileNotFoundError):
                annotation.session(result['annotation_id'], str(output))
        self.assertFalse(captured.parent.exists())
        self.assertEqual(output.read_bytes(), b'existing saved image')

    def test_annotation_worker_cleans_input_after_editor_exit_and_preserves_save(self):
        output = self.root / 'saved.png'
        result = annotation.launch(b'private image', output, Mock())
        captured = self.root / 'runtime/sumi/annotations' / result['annotation_id'] / 'capture.png'
        process = Mock()
        process.poll.return_value = 0
        def editor_exit():
            self.assertEqual(captured.read_bytes(), b'private image')
            self.assertFalse(output.exists())
            output.write_bytes(b'user saved annotation')
            return 0
        process.wait.side_effect = editor_exit
        with patch('sumi.annotation.subprocess.Popen', return_value=process) as launch:
            main(['annotation-session', result['annotation_id'], str(output)])
        launch.assert_called_once_with(['satty', '--filename', str(captured), '--output-filename', str(output)])
        self.assertFalse(captured.parent.exists())
        self.assertEqual(output.read_bytes(), b'user saved annotation')

    def test_annotation_worker_interruption_stops_only_its_editor_before_cleanup(self):
        output = self.root / 'saved.png'
        result = annotation.launch(b'private image', output, Mock())
        captured = self.root / 'runtime/sumi/annotations' / result['annotation_id'] / 'capture.png'
        process = Mock()
        process.poll.return_value = None
        def interrupted_wait(timeout=None):
            self.assertTrue(captured.exists(), 'Keep input until the editor is stopped')
            if timeout is None:
                raise KeyboardInterrupt()
            process.terminate.assert_called_once_with()
            return 0
        process.wait.side_effect = interrupted_wait
        previous = signal.getsignal(signal.SIGTERM)
        with patch('sumi.annotation.subprocess.Popen', return_value=process):
            with self.assertRaises(KeyboardInterrupt):
                annotation.session(result['annotation_id'], str(output))
        self.assertFalse(captured.parent.exists())
        self.assertFalse(output.exists())
        self.assertIs(signal.getsignal(signal.SIGTERM), previous)

    def test_annotation_rejects_unowned_paths_without_deleting_them(self):
        target = self.root / 'keep.png'
        target.write_bytes(b'private unrelated image')
        with patch('sumi.annotation.subprocess.Popen') as launch:
            for identifier in ('../keep.png', str(target), 'not-a-session'):
                with self.subTest(identifier=identifier), self.assertRaisesRegex(ValueError, 'Invalid annotation'):
                    annotation.session(identifier, str(self.root / 'out.png'))
            result = annotation.launch(b'private image', self.root / 'out.png', Mock())
            captured = self.root / 'runtime/sumi/annotations' / result['annotation_id'] / 'capture.png'
            captured.unlink()
            captured.symlink_to(target)
            with self.assertRaises(OSError):
                annotation.session(result['annotation_id'], str(self.root / 'out.png'))
            launch.assert_not_called()
        self.assertTrue(captured.is_symlink())
        self.assertEqual(target.read_bytes(), b'private unrelated image')

    def test_annotation_capture_returns_while_synthetic_editor_remains_open(self):
        image = b'\x89PNG\r\n\x1a\n' + b'image data' + b'\x00\x00\x00\x00IEND\xaeB`\x82'
        editor = self.root / 'satty'
        editor.write_text(f'''#!{sys.executable}
from pathlib import Path
import sys
import time
work = Path(__file__).parent
arguments = sys.argv
captured = Path(arguments[arguments.index("--filename") + 1])
output = Path(arguments[arguments.index("--output-filename") + 1])
(work / "editor-ready").write_text("ready")
deadline = time.monotonic() + 8
while not (work / "editor-release").exists():
    if time.monotonic() >= deadline:
        raise SystemExit(2)
    time.sleep(.01)
output.write_bytes(captured.read_bytes())
''')
        editor.chmod(0o700)
        workers = []
        def independent_worker(arguments):
            # Replace only the transient-unit launcher; the real CLI and
            # annotation worker run in a child with a synthetic Satty binary.
            workers.append(subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        environment = dict(PATH=str(self.root) + os.pathsep + os.environ['PATH'], SUMI_HOME=str(self.root))
        try:
            with patch.dict(os.environ, environment), patch('sumi.actions.Path.home', return_value=self.root), patch('sumi.actions.subprocess.run', return_value=subprocess.CompletedProcess([], 1, image, b'')), patch('sumi.actions.spawn', side_effect=independent_worker):
                result = capture(['output', 'annotate'])
            self.assertTrue(result['launched'])
            self.assertEqual(len(workers), 1)
            worker = workers[0]
            deadline = time.monotonic() + 5
            while not (self.root / 'editor-ready').exists():
                if worker.poll() is not None:
                    self.fail('Synthetic annotation worker failed: ' + repr(worker.communicate()))
                if time.monotonic() >= deadline:
                    self.fail('Synthetic editor failed to open')
                time.sleep(.01)
            self.assertIsNone(worker.poll(), 'Interactive editor must outlive capture()')
            captured = self.root / 'runtime/sumi/annotations' / result['annotation_id'] / 'capture.png'
            self.assertEqual(captured.read_bytes(), image)
            self.assertFalse(Path(result['output']).exists())
            (self.root / 'editor-release').touch()
            _, errors = worker.communicate(timeout=5)
            self.assertEqual(worker.returncode, 0, errors.decode())
            self.assertFalse(captured.parent.exists())
            self.assertEqual(Path(result['output']).read_bytes(), image)
        finally:
            (self.root / 'editor-release').touch()
            for worker in workers:
                if worker.poll() is None:
                    worker.terminate()
                    worker.communicate(timeout=7)

    def test_recording_recovers_after_its_previous_process_exits(self):
        process = Mock(pid=77777)
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired('wf-recorder', .35)
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, XDG_RUNTIME_DIR=folder), patch('sumi.actions.Path.home', return_value=Path(folder)), patch('sumi.actions.run', return_value=Mock(stdout='0,0 100x100')), patch('sumi.actions.subprocess.Popen', return_value=process), patch('sumi.actions._recorder_running', side_effect=lambda data: data.get('pid') == 77777):
            pidfile = Path(folder) / 'sumi' / 'recorder.json'
            pidfile.parent.mkdir()
            pidfile.write_text(json.dumps({'pid': 999999999, 'file': '/tmp/old.mp4'}))
            recording('start')
            self.assertEqual(json.loads(pidfile.read_text())['pid'], 77777)

    def test_clipboard_status_does_not_call_one_active_watcher_paused(self):
        states = [subprocess.CompletedProcess([], 3, 'inactive\n', ''), subprocess.CompletedProcess([], 0, 'active\n', '')]
        with patch('sumi.actions.subprocess.run', side_effect=states), patch('sys.stdout', new_callable=StringIO) as output:
            clipboard(['status'])
        state = json.loads(output.getvalue())
        self.assertFalse(state['paused'])
        self.assertFalse(state['textActive'])
        self.assertTrue(state['imageActive'])
        self.assertFalse(state['healthy'])

    def test_clipboard_pause_is_persisted_only_after_both_watchers_stop(self):
        with patch('sumi.actions.run'), patch('sumi.actions.subprocess.run', return_value=subprocess.CompletedProcess([], 3, 'inactive\n', '')), patch('sys.stdout', new_callable=StringIO) as output:
            clipboard(['pause'])
        self.assertTrue(json.loads(output.getvalue())['paused'])
        self.assertEqual(json.loads((self.root / 'state/clipboard.json').read_text())['paused'], True)
        with patch('sumi.actions.run') as run, patch('sumi.actions.subprocess.run', return_value=subprocess.CompletedProcess([], 3, 'inactive\n', '')), patch.dict(os.environ, SUMI_DRY_RUN='0'):
            actions.restore_clipboard_watchers()
        self.assertEqual(run.call_args.args[0][2], 'stop')

    def test_clipboard_partial_failure_does_not_persist_or_report_success(self):
        states = [subprocess.CompletedProcess([], 3, 'inactive\n', ''), subprocess.CompletedProcess([], 0, 'active\n', '')]
        with patch('sumi.actions.run'), patch('sumi.actions.subprocess.run', side_effect=states), patch('sys.stdout', new_callable=StringIO) as output:
            with self.assertRaisesRegex(RuntimeError, 'did not both stop'):
                clipboard(['pause'])
        self.assertFalse((self.root / 'state/clipboard.json').exists())
        self.assertEqual(output.getvalue(), '')

    def test_clipboard_restore_dry_run_never_touches_service_manager(self):
        with patch('sumi.actions.run') as run, patch('sumi.actions.subprocess.run') as subprocess_run, patch.dict(os.environ, SUMI_DRY_RUN='1'):
            self.assertTrue(actions.restore_clipboard_watchers()['dry_run'])
        run.assert_not_called()
        subprocess_run.assert_not_called()

    def test_explicit_clipboard_choice_repairs_malformed_preference(self):
        preference = self.root / 'state/clipboard.json'
        preference.parent.mkdir()
        for command, paused, state in (('pause', True, 'inactive'), ('resume', False, 'active')):
            for invalid in ('{invalid', '{"paused":"yes"}'):
                with self.subTest(command=command, invalid=invalid):
                    preference.write_text(invalid)
                    with patch('sumi.actions.run'), patch('sumi.actions.subprocess.run', return_value=subprocess.CompletedProcess([], 0 if not paused else 3, state + '\n', '')), patch('sys.stdout', new_callable=StringIO) as output:
                        clipboard([command])
                    self.assertEqual(json.loads(preference.read_text())['paused'], paused)
                    result = json.loads(output.getvalue())
                    self.assertEqual(result['paused'], paused)
                    self.assertTrue(result['healthy'])

    def test_clipboard_startup_refuses_malformed_preference_before_service_changes(self):
        preference = self.root / 'state/clipboard.json'
        preference.parent.mkdir()
        for invalid in ('{invalid', '{"paused":"yes"}'):
            with self.subTest(invalid=invalid):
                preference.write_text(invalid)
                with patch.dict(os.environ, SUMI_DRY_RUN='0'), patch('sumi.actions.run') as run, patch('sumi.actions.subprocess.run') as subprocess_run:
                    with self.assertRaisesRegex(RuntimeError, 'history was not resumed'):
                        actions.restore_clipboard_watchers()
                run.assert_not_called()
                subprocess_run.assert_not_called()
                self.assertEqual(preference.read_text(), invalid)

    def test_failed_application_registration_propagates(self):
        failure = subprocess.CalledProcessError(1, ['systemd-run'], stderr='Start failed')
        with patch('sumi.actions.shutil.which', return_value='/usr/bin/kitty'), patch('sumi.actions.run', side_effect=failure):
            with self.assertRaises(subprocess.CalledProcessError):
                actions.spawn(['kitty'])

    def test_application_launch_waits_for_exec_registration_not_application_exit(self):
        with patch('sumi.actions.shutil.which', return_value='/example/desktopctl'), patch('sumi.actions.run') as run:
            actions.spawn(['/example/desktopctl', 'action', 'annotation-session', 'a' * 32, '/tmp/output with spaces.png'])
        arguments = run.call_args.args[0]
        self.assertEqual(arguments[:5], ['systemd-run', '--user', '--collect', '--quiet', '--service-type=exec'])
        self.assertNotIn('--wait', arguments)
        self.assertEqual(arguments[arguments.index('--') + 1:], ['/example/desktopctl', 'action', 'annotation-session', 'a' * 32, '/tmp/output with spaces.png'])

    def test_recording_lock_covers_interactive_selection(self):
        def select(*args, **kwargs):
            with self.assertRaisesRegex(RuntimeError, 'already running'):
                recording('start')
            return Mock(stdout='')
        with patch('sumi.actions.run', side_effect=select), patch('sumi.actions.subprocess.Popen') as spawn:
            self.assertTrue(recording('start')['cancelled'])
        spawn.assert_not_called()

    def test_failed_recorder_start_is_not_published(self):
        process = Mock(pid=77777)
        process.poll.return_value = 1
        process.wait.return_value = 1
        with patch('sumi.actions.Path.home', return_value=self.root), patch('sumi.actions.run', return_value=Mock(stdout='0,0 100x100')), patch('sumi.actions.subprocess.Popen', return_value=process):
            with self.assertRaisesRegex(RuntimeError, 'failed to start'):
                recording('start')
        self.assertFalse((self.root / 'runtime/sumi/recorder.json').exists())

    def test_recording_tracking_failure_stops_new_process(self):
        real_write = actions.atomic_write
        def fail_tracking(path, content, *args):
            if path.name == 'recorder.json':
                raise OSError('disk full')
            return real_write(path, content, *args)
        process = Mock(pid=77777)
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired('wf-recorder', .35), 0]
        with patch('sumi.actions.Path.home', return_value=self.root), patch('sumi.actions.run', return_value=Mock(stdout='0,0 100x100')), patch('sumi.actions.subprocess.Popen', return_value=process), patch('sumi.actions._recorder_running', side_effect=lambda data: data.get('pid') == 77777), patch('sumi.actions.atomic_write', side_effect=fail_tracking):
            with self.assertRaisesRegex(OSError, 'disk full'):
                recording('start')
        process.send_signal.assert_called_once()

    def test_recording_readiness_interruption_cleans_tracked_child(self):
        process = Mock(pid=77777)
        process.poll.return_value = None
        pidfile = self.root / 'runtime/sumi/recorder.json'
        def interrupted_wait(*, timeout):
            if timeout == .35:
                self.assertEqual(json.loads(pidfile.read_text())['pid'], 77777)
                raise KeyboardInterrupt()
            return 0
        process.wait.side_effect = interrupted_wait
        previous = signal.getsignal(signal.SIGTERM)
        with patch('sumi.actions.Path.home', return_value=self.root), patch('sumi.actions.run', return_value=Mock(stdout='0,0 100x100')), patch('sumi.actions.subprocess.Popen', return_value=process):
            with self.assertRaises(KeyboardInterrupt):
                recording('start')
        process.send_signal.assert_called_once_with(signal.SIGINT)
        self.assertFalse(pidfile.exists())
        self.assertIs(signal.getsignal(signal.SIGTERM), previous)

    @unittest.skipUnless(shutil.which('cc'), 'C compiler required for synthetic recorder interruption test')
    def test_sigterm_during_recorder_readiness_leaves_no_orphan(self):
        source = self.root / 'recorder.c'
        source.write_text('''#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
int main(void) {
    FILE *file = fopen(getenv("SUMI_TEST_RECORDER_PID"), "w");
    if (!file) return 2;
    fprintf(file, "%d", getpid());
    fclose(file);
    for (;;) pause();
}
''')
        executable = self.root / 'wf-recorder'
        subprocess.run(['cc', str(source), '-o', str(executable)], check=True, capture_output=True, timeout=15)
        driver = self.root / 'driver.py'
        library = Path(actions.__file__).resolve().parents[1]
        driver.write_text(f'''import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock, patch
sys.path.insert(0, {str(library)!r})
from sumi import actions
work = Path(__file__).parent
original_wait = subprocess.Popen.wait
def observed_wait(process, timeout=None):
    if timeout == .35:
        (work / "readiness-entered").write_text("ready")
    return original_wait(process, timeout=timeout)
with patch("sumi.actions.run", return_value=Mock(stdout="0,0 100x100")), patch("sumi.actions.Path.home", return_value=work), patch.object(subprocess.Popen, "wait", observed_wait):
    actions.recording("start")
''')
        environment = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ['PATH'],
                           SUMI_TEST_RECORDER_PID=str(self.root / 'child.pid'))
        controller = subprocess.Popen([sys.executable, str(driver)], env=environment,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        child = None
        try:
            deadline = time.monotonic() + 5
            while True:
                if (self.root / 'readiness-entered').exists() and (self.root / 'child.pid').exists():
                    try:
                        child = int((self.root / 'child.pid').read_text())
                        break
                    except ValueError:
                        pass
                if controller.poll() is not None:
                    self.fail('Synthetic controller exited before readiness: ' + repr(controller.communicate()))
                if time.monotonic() >= deadline:
                    self.fail('Synthetic recorder did not reach readiness')
                time.sleep(.005)
            pidfile = self.root / 'runtime/sumi/recorder.json'
            self.assertTrue(pidfile.exists(), 'Recorder must be recoverable before readiness waiting')
            tracked = json.loads(pidfile.read_text())
            self.assertEqual(tracked['pid'], child)
            controller.terminate()
            controller.communicate(timeout=8)
            self.assertNotEqual(controller.returncode, 0)
            self.assertFalse(actions._recorder_running(tracked), 'SIGTERM left a recorder alive')
            self.assertFalse(recording('stop')['recording'])
            self.assertFalse(pidfile.exists())
        finally:
            if controller.poll() is None:
                controller.terminate()
                controller.communicate(timeout=8)
            if child is not None:
                try:
                    command = Path(f'/proc/{child}/cmdline').read_bytes().split(b'\0')
                    if command and command[0] == os.fsencode(executable):
                        os.kill(child, signal.SIGTERM)
                except (FileNotFoundError, ProcessLookupError):
                    pass

    def test_recording_stop_timeout_preserves_tracking(self):
        pidfile = self.root / 'runtime/sumi/recorder.json'
        pidfile.parent.mkdir(parents=True)
        pidfile.write_text(json.dumps({'pid': 77777, 'file': '/tmp/test.mp4'}))
        with patch('sumi.actions._recorder_running', return_value=True), patch('sumi.actions.os.kill') as kill, patch('sumi.actions.time.monotonic', side_effect=[0, 6]):
            with self.assertRaisesRegex(RuntimeError, 'tracking was retained'):
                recording('stop')
        self.assertTrue(pidfile.exists())
        kill.assert_called_once()

    @patch('sumi.actions.spawn')
    def test_ghostty_desktop_entry_avoids_broken_vendor_service(self, spawn):
        main(['launch-desktop', 'com.mitchellh.ghostty.desktop'])
        spawn.assert_called_once_with(['ghostty', '--gtk-single-instance=false'])

    @patch('sumi.actions.spawn')
    def test_terminal_keeps_directory_arguments_as_separate_values(self, spawn):
        main(['terminal', '--working-directory=/tmp/a b'])
        spawn.assert_called_once_with(['kitty', '--single-instance', '--directory=/tmp/a b'])

    @patch('sumi.actions.spawn')
    def test_managers_launch_without_teaching_launcher_history(self, spawn):
        main(['audio-manager'])
        spawn.assert_called_with(['pwvucontrol'])
        main(['bluetooth-manager'])
        spawn.assert_called_with(['blueman-manager'])
        self.assertFalse((self.root / 'state/launcher-history.json').exists())

    def test_brightness_read_reports_actual_zero_and_never_invents_a_default(self):
        with patch('sumi.actions.run', return_value=subprocess.CompletedProcess([], 0, 'intel_backlight,backlight,0,0%,1000\n')), patch('sys.stdout', new_callable=StringIO) as output:
            main(['brightness-get'])
        self.assertEqual(json.loads(output.getvalue()), {'percent': 0})
        for invalid in ('', 'missing', 'intel,backlight,30,none,100', 'intel,backlight,101,101%,100', 'intel,backlight,0,50%,0'):
            with self.subTest(output=invalid), patch('sumi.actions.run', return_value=subprocess.CompletedProcess([], 0, invalid)):
                with self.assertRaises(RuntimeError):
                    main(['brightness-get'])

    def test_night_light_capability_and_inactive_daemon(self):
        with patch('sumi.actions.shutil.which', return_value=None):
            self.assertEqual(actions.night_light_state(), {'available': False, 'active': False, 'temperature': None})
        with patch('sumi.actions.shutil.which', return_value='/usr/bin/tool'), patch('sumi.actions.subprocess.run', side_effect=[
                subprocess.CompletedProcess([], 1, '', 'socket unavailable'), subprocess.CompletedProcess([], 1, '', '')]):
            self.assertEqual(actions.night_light_state(), {'available': True, 'active': False, 'temperature': None})

    def test_night_light_reports_observed_temperature_and_read_failure(self):
        with patch('sumi.actions.shutil.which', return_value='/usr/bin/tool'), patch('sumi.actions.subprocess.run', return_value=subprocess.CompletedProcess([], 0, '4200\n', '')):
            self.assertEqual(actions.night_light_state(), {'available': True, 'active': True, 'temperature': 4200})
        with patch('sumi.actions.shutil.which', return_value='/usr/bin/tool'), patch('sumi.actions.subprocess.run', side_effect=[
                subprocess.CompletedProcess([], 1, '', 'socket unavailable'), subprocess.CompletedProcess([], 0, '1234', '')]):
            with self.assertRaisesRegex(RuntimeError, 'could not be read'):
                actions.night_light_state()
        with patch('sumi.actions.shutil.which', return_value='/usr/bin/tool'), patch('sumi.actions.subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'invalid', '')):
            with self.assertRaisesRegex(RuntimeError, 'invalid temperature'):
                actions.night_light_state()

    def test_night_light_waits_for_observed_state_after_start(self):
        inactive = {'available': True, 'active': False, 'temperature': None}
        active = {'available': True, 'active': True, 'temperature': 4200}
        with patch('sumi.actions.night_light_state', side_effect=[inactive, inactive, active]), patch('sumi.actions.spawn') as launch, patch('sumi.actions.time.sleep'), patch('sys.stdout', new_callable=StringIO) as output:
            main(['night-light'])
        launch.assert_called_once_with(['hyprsunset', '-t', '4200'])
        self.assertEqual(json.loads(output.getvalue()), active)

    def test_night_light_does_not_claim_success_when_readback_disagrees(self):
        active = {'available': True, 'active': True, 'temperature': 4200}
        with patch('sumi.actions.night_light_state', return_value=active), patch('sumi.actions.run') as call, patch('sumi.actions.time.sleep'):
            with self.assertRaisesRegex(RuntimeError, 'did not confirm'):
                main(['night-light'])
        self.assertEqual(call.call_args.args[0], ['hyprctl', 'hyprsunset', 'temperature', '6500'])

    def test_search_ignores_dependency_trees_and_does_not_follow_links(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            project = home / 'Coading' / 'demo'
            (project / 'node_modules').mkdir(parents=True)
            (project / 'report.pdf').touch()
            (project / 'node_modules' / 'report-secret.pdf').touch()
            (home / 'Downloads').mkdir()
            (home / 'Downloads' / 'link').symlink_to(project, target_is_directory=True)
            result = search_files('report', home)
            self.assertEqual([x['name'] for x in result], ['report.pdf'])

    def test_short_queries_do_not_scan(self):
        self.assertEqual(search_files('a'), [])

    @patch('sumi.actions.shutil.which', return_value='/usr/bin/cliphist')
    def test_clipboard_rejects_command_like_identifiers(self, _which):
        with self.assertRaises(ValueError):
            clipboard(['copy', '1;rm -rf /'])

    @patch('sumi.actions.run')
    def test_brightness_is_bounded(self, call):
        main(['brightness', '500'])
        self.assertEqual(call.call_args.args[0], ['brightnessctl', 'set', '100%'])
