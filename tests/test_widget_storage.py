import copy
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from sumi import widgets


class WidgetStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state = Path(self.temporary.name) / "state"
        self.path = self.state / "widgets.json"
        self.repo = Path(__file__).resolve().parents[1]
        self.environment = dict(os.environ, SUMI_HOME=self.temporary.name, SUMI_STATE_DIR=str(self.state))

    def cli(self, command, payload=None):
        return subprocess.run([str(self.repo / "bin/desktopctl"), "widgets", command, "--json"],
                              input=payload, env=self.environment, text=True, capture_output=True, timeout=5)

    def test_missing_state_has_fresh_empty_defaults(self):
        loaded = widgets.load(self.state)
        self.assertEqual(loaded, widgets.defaults())
        self.assertEqual(len(loaded["priorities"]), 3)
        self.assertTrue(all(loaded["enabled"].values()))
        loaded["priorities"][0]["text"] = "Local change"
        self.assertEqual(widgets.defaults()["priorities"][0]["text"], "")
        self.assertFalse(self.path.exists())

    def test_round_trip_is_private_and_preserves_local_content(self):
        document = widgets.defaults()
        document["priorities"][0] = {"text": "Review 📝 $(touch ignored)", "done": True}
        document["deadline"] = {"title": "Demo", "at": 1_798_000_000_000}
        document["enabled"]["spotify"] = False
        document["layouts"] = {"sha256:example": "split", "another-image": "right"}
        self.assertEqual(widgets.save(document, self.state), {"saved": True, "version": 1})
        self.assertEqual(widgets.load(self.state), document)
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.state / "widgets.lock").stat().st_mode), 0o600)
        document["layouts"].pop("sha256:example")
        widgets.save(document, self.state)
        self.assertNotIn("sha256:example", widgets.load(self.state)["layouts"])

    def test_invalid_documents_never_replace_saved_content(self):
        widgets.save(widgets.defaults(), self.state)
        original = self.path.read_bytes()
        invalid = [None, [], {"version": 1}]
        changes = [
            ("version", True), ("version", 2), ("version", 1.0),
            ("enabled", {"clock": True}),
            ("priorities", []), ("priorities", [{"text": "", "done": False}] * 4),
            ("deadline", {"title": "x" * 161, "at": None}),
            ("layouts", {"": "left"}), ("layouts", {"x" * 513: "left"}),
            ("layouts", {"image": "auto"}), ("layouts", {str(i): "left" for i in range(257)}),
        ]
        for key, value in changes:
            document = widgets.defaults()
            document[key] = value
            invalid.append(document)
        for at in ("tomorrow", True, -1, float("nan"), float("inf"), 1.5, 10 ** 400):
            document = widgets.defaults()
            document["deadline"]["at"] = at
            invalid.append(document)
        for task in ({"text": "x" * 181, "done": False}, {"text": "", "done": 1},
                     {"text": "", "done": False, "extra": True}, {"text": "bad\0text", "done": False}):
            document = widgets.defaults()
            document["priorities"][0] = task
            invalid.append(document)
        enabled = widgets.defaults()
        enabled["enabled"]["clock"] = "true"
        invalid.append(enabled)
        for value in invalid:
            with self.subTest(value=str(value)[:120]), self.assertRaises(ValueError):
                widgets.save(value, self.state)
            self.assertEqual(self.path.read_bytes(), original)

    def test_normalize_does_not_mutate_or_share_input(self):
        document = widgets.defaults()
        document["deadline"]["at"] = 42.0
        original = copy.deepcopy(document)
        normalized = widgets.normalize(document)
        self.assertEqual(document, original)
        self.assertIs(type(normalized["deadline"]["at"]), int)
        normalized["priorities"][0]["done"] = True
        normalized["enabled"]["clock"] = False
        normalized["layouts"]["image"] = "left"
        self.assertEqual(document, original)

    def test_malformed_or_oversize_state_fails_without_overwriting_it(self):
        self.state.mkdir()
        for payload in (b"{broken", b"[]", b" " * (widgets.MAX_STORAGE_BYTES + 1), b"\xff"):
            with self.subTest(size=len(payload)):
                self.path.write_bytes(payload)
                with self.assertRaises(ValueError):
                    widgets.load(self.state)
                self.assertEqual(self.path.read_bytes(), payload)

    def test_failed_atomic_replace_preserves_previous_document(self):
        widgets.save(widgets.defaults(), self.state)
        original = self.path.read_bytes()
        document = widgets.defaults()
        document["deadline"]["title"] = "A change"
        with patch("sumi.statefiles.os.replace", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                widgets.save(document, self.state)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.state.glob(".widgets.json.*")), [])

    def test_cli_uses_stdin_and_survives_a_new_process(self):
        document = widgets.defaults()
        document["priorities"][0]["text"] = "Private task"
        saved = self.cli("save", json.dumps(document))
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertTrue(json.loads(saved.stdout)["saved"])
        self.assertNotIn("Private task", saved.stdout + saved.stderr)
        loaded = self.cli("load")
        self.assertEqual(loaded.returncode, 0, loaded.stderr)
        self.assertEqual(json.loads(loaded.stdout), document)

    def test_cli_rejects_invalid_input_without_overwrite(self):
        widgets.save(widgets.defaults(), self.state)
        original = self.path.read_bytes()
        for payload in ("{broken", "null", " " * (widgets.MAX_STORAGE_BYTES + 1)):
            result = self.cli("save", payload)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(self.path.read_bytes(), original)
        self.path.write_text("{broken")
        result = self.cli("load")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.path.read_text(), "{broken")


if __name__ == "__main__":
    unittest.main()
