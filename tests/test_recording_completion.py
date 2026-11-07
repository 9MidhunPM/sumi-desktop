"""A stale recording receipt must never become a successful-save message."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sumi.actions import recording


class RecordingCompletionTests(unittest.TestCase):
    def test_stale_receipt_does_not_claim_an_owned_recorder_was_stopped(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}):
            runtime = Path(directory) / "sumi"
            runtime.mkdir()
            (runtime / "recorder.json").write_text(json.dumps({"pid": 123, "file": "/tmp/fixture.mp4"}))
            with patch("sumi.actions._recorder_running", return_value=False), patch("sumi.actions.os.kill") as kill:
                result = recording("stop")
            self.assertFalse(result["recording"])
            self.assertFalse(result["stopped"])
            kill.assert_not_called()

    def test_confirmed_owned_stop_is_distinguishable_from_receipt_cleanup(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}):
            runtime = Path(directory) / "sumi"
            runtime.mkdir()
            (runtime / "recorder.json").write_text(json.dumps({"pid": 123, "file": "/tmp/fixture.mp4"}))
            with patch("sumi.actions._recorder_running", side_effect=[True, False]), patch("sumi.actions.os.kill") as kill:
                result = recording("stop")
            self.assertTrue(result["stopped"])
            self.assertFalse(result["recording"])
            kill.assert_called_once()

    def test_recorder_exit_during_stop_is_not_reported_as_a_save(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}):
            runtime = Path(directory) / "sumi"
            runtime.mkdir()
            (runtime / "recorder.json").write_text(json.dumps({"pid": 123, "file": "/tmp/fixture.mp4"}))
            with patch("sumi.actions._recorder_running", side_effect=[True, False]), patch("sumi.actions.os.kill", side_effect=ProcessLookupError):
                result = recording("stop")
            self.assertFalse(result["stopped"])


if __name__ == "__main__":
    unittest.main()
