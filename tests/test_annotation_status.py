import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sumi import annotation


class AnnotationStatusTests(unittest.TestCase):
    def test_lifecycle_is_owned_and_does_not_read_image(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, XDG_RUNTIME_DIR=tmp):
            identifier = 'a' * 32
            self.assertEqual(annotation.status(identifier), {'active': False})
            folder = Path(tmp) / 'sumi/annotations' / identifier
            folder.mkdir(parents=True, mode=0o700)
            folder.parent.chmod(0o700)
            (folder / 'capture.png').write_bytes(b'private image')
            self.assertEqual(annotation.status(identifier), {'active': True})
            (folder / 'capture.png').unlink()
            folder.rmdir()
            self.assertEqual(annotation.status(identifier), {'active': False})

    def test_rejects_paths_and_unowned_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, XDG_RUNTIME_DIR=tmp):
            for identifier in ('../x', '/tmp/x', '', 'a' * 33):
                with self.assertRaises(ValueError):
                    annotation.status(identifier)
            folder = Path(tmp) / 'sumi/annotations'
            folder.mkdir(parents=True, mode=0o700)
            target = Path(tmp) / 'unrelated'
            target.mkdir()
            (folder / ('b' * 32)).symlink_to(target, target_is_directory=True)
            with self.assertRaises(OSError):
                annotation.status('b' * 32)
            self.assertTrue(target.exists())

    def test_abandoned_worker_releases_handoff_and_only_cleans_owned_input(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, XDG_RUNTIME_DIR=tmp):
            identifier = 'c' * 32
            folder = Path(tmp) / 'sumi/annotations' / identifier
            folder.mkdir(parents=True, mode=0o700)
            folder.parent.chmod(0o700)
            (folder / 'capture.png').write_bytes(b'private input')
            (folder / 'owner.json').write_text(json.dumps({'pid': os.getpid(), 'start': 'not-this-process'}))
            saved = Path(tmp) / 'saved.png'
            saved.write_bytes(b'user output')
            self.assertEqual(annotation.status(identifier), {'active': False})
            self.assertFalse(folder.exists())
            self.assertEqual(saved.read_bytes(), b'user output')

    def test_live_editor_has_no_session_deadline(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, XDG_RUNTIME_DIR=tmp):
            folder = Path(tmp) / 'sumi/annotations' / ('d' * 32)
            folder.mkdir(parents=True, mode=0o700)
            folder.parent.chmod(0o700)
            (folder / 'owner.json').write_text(json.dumps({'pid': os.getpid(), 'start': annotation._process_start(os.getpid())}))
            os.utime(folder, (0, 0))
            self.assertEqual(annotation.status('d' * 32), {'active': True})
