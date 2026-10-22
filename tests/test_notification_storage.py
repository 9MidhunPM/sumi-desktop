import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

from sumi import notifications


class NotificationStorageTests(unittest.TestCase):
    def test_history_is_private_bounded_and_drops_live_actions_and_transients(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "state"
            entries = [dict(id=i, summary=f"Message {i}", body="Body", unread=True,
                            popup=True, actions=["Open"], time="2026-10-21T12:00:00Z") for i in range(105)]
            entries[1]["transient"] = True
            notifications.save(entries, state)
            loaded = notifications.load(state)["entries"]
            self.assertEqual(len(loaded), 99)
            self.assertEqual(loaded[0]["summary"], "Message 0")
            self.assertTrue(loaded[0]["unread"])
            self.assertNotIn("popup", loaded[0])
            self.assertNotIn("actions", loaded[0])
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((state / "notifications.json").stat().st_mode), 0o600)
            notifications.save([], state)
            self.assertEqual(notifications.load(state)["entries"], [])

    def test_cli_reads_history_from_stdin_and_survives_a_new_process(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            environment = dict(os.environ, SUMI_HOME=temporary, SUMI_STATE_DIR=temporary + "/state")
            payload = [{"id": 5, "summary": "Persisted", "body": "Private body", "unread": True}]
            saved = subprocess.run([str(repo / "bin/desktopctl"), "notifications", "save"],
                                   input=json.dumps(payload), env=environment, text=True, capture_output=True, timeout=5)
            self.assertEqual(saved.returncode, 0, saved.stderr)
            loaded = subprocess.run([str(repo / "bin/desktopctl"), "notifications", "load"],
                                    env=environment, text=True, capture_output=True, timeout=5)
            self.assertEqual(loaded.returncode, 0, loaded.stderr)
            self.assertEqual(json.loads(loaded.stdout)["entries"][0]["body"], "Private body")


if __name__ == "__main__":
    unittest.main()
