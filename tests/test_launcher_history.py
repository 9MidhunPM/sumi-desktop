import concurrent.futures
import copy
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from sumi import launcher_history as history


class LauncherHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state = Path(self.temporary.name) / "state"
        self.path = self.state / "launcher-history.json"
        self.repo = Path(__file__).resolve().parents[1]
        self.environment = dict(os.environ, SUMI_HOME=self.temporary.name, SUMI_STATE_DIR=str(self.state))

    def cli(self, command, payload=None):
        return subprocess.run([str(self.repo / "bin/desktopctl"), "launcher-history", command, "--json"],
                              input=payload, env=self.environment, text=True, capture_output=True, timeout=10)

    def test_missing_history_is_empty_and_private(self):
        self.assertEqual(history.load(self.state), {"version": 1, "entries": {}})
        self.assertFalse(self.path.exists())
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o700)

    def test_records_choices_by_stable_id_with_normalized_queries_and_decay(self):
        first = history.record({"id": "app:brave-youtube.desktop", "query": "  YOU \n Tube  "}, self.state, now=100)
        second = history.record({"id": "app:brave-youtube", "query": "you tube"}, self.state,
                                now=100 + history.HALF_LIFE_SECONDS)
        entry = second["entries"]["app:brave-youtube"]
        self.assertEqual(entry["count"], 2)
        self.assertEqual(entry["score"], 1.5)
        self.assertEqual(entry["queries"]["you tube"]["score"], 1.5)
        self.assertEqual(first["entries"]["app:brave-youtube"]["count"], 1)
        third = history.record({"id": "app:firefox-youtube", "query": "You"}, self.state, now=200)
        self.assertEqual(len(third["entries"]), 2)
        self.assertEqual(history.load(self.state), third)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.state / "launcher-history.lock").stat().st_mode), 0o600)

    def test_empty_query_records_only_general_usage_and_clock_rollback_does_not_amplify_score(self):
        history.record({"id": "action:settings", "query": ""}, self.state, now=200)
        result = history.record({"id": "action:settings", "query": " \t "}, self.state, now=100)
        self.assertEqual(result["entries"]["action:settings"], {"count": 2, "score": 2, "lastUsed": 100, "queries": {}})

    def test_queries_and_entries_are_bounded_with_recent_choice_retained(self):
        value = history.defaults()
        for index in range(history.MAX_ENTRIES):
            value["entries"][f"app:fixture-{index:04}"] = {"count": 1, "score": 1, "lastUsed": index, "queries": {}}
        self.state.mkdir()
        self.path.write_text(json.dumps(value))
        for index in range(history.MAX_QUERIES + 2):
            result = history.record({"id": "app:new", "query": f"query {index:02}"}, self.state, now=1000 + index)
        self.assertEqual(len(result["entries"]), history.MAX_ENTRIES)
        self.assertNotIn("app:fixture-0000", result["entries"])
        queries = result["entries"]["app:new"]["queries"]
        self.assertEqual(len(queries), history.MAX_QUERIES)
        self.assertNotIn("query 00", queries)
        self.assertIn("query 33", queries)
        result = history.record({"id": "app:new", "query": "y" * 200}, self.state, now=2000)
        self.assertIn("y" * history.MAX_QUERY_LENGTH, result["entries"]["app:new"]["queries"])

    def test_invalid_requests_do_not_change_existing_history(self):
        history.record({"id": "app:kitty", "query": "kitty"}, self.state, now=100)
        original = self.path.read_bytes()
        invalid = [None, [], {}, {"id": "app:kitty"}, {"id": "app:kitty", "query": 1},
                   {"id": "app:", "query": ""}, {"id": "file:/private/file", "query": ""},
                   {"id": "action:unknown", "query": ""}, {"id": "app:kitty", "query": "bad\0query"},
                   {"id": "app:kitty", "query": "", "time": 100}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                history.record(value, self.state)
            self.assertEqual(self.path.read_bytes(), original)

    def test_malformed_history_survives_load_and_record_until_explicit_reset(self):
        self.state.mkdir()
        invalid_documents = [b"{broken", b"[]", b"\xff", json.dumps({"version": True, "entries": {}}).encode()]
        good = {"version": 1, "entries": {"app:kitty": {"count": 1, "score": 1, "lastUsed": 1, "queries": {}}}}
        for field, invalid in (("count", True), ("count", -1), ("score", float("nan")),
                               ("score", float("inf")), ("lastUsed", -1), ("queries", [])):
            value = copy.deepcopy(good)
            value["entries"]["app:kitty"][field] = invalid
            invalid_documents.append(json.dumps(value).encode())
        for payload in invalid_documents:
            self.path.write_bytes(payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                history.load(self.state)
            with self.assertRaises(ValueError):
                history.record({"id": "app:kitty", "query": "kitty"}, self.state)
            self.assertEqual(self.path.read_bytes(), payload)
        self.assertEqual(history.reset(self.state), history.defaults())
        self.assertEqual(history.load(self.state), history.defaults())

    def test_failed_atomic_replace_preserves_previous_document(self):
        history.record({"id": "app:kitty", "query": "kitty"}, self.state, now=100)
        original = self.path.read_bytes()
        with patch("sumi.statefiles.os.replace", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                history.record({"id": "app:kitty", "query": "kitty"}, self.state, now=101)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.state.glob(".launcher-history.json.*")), [])

    def test_cli_stdin_persistence_and_reset_across_processes(self):
        payload = json.dumps({"id": "action:settings", "query": "  Sound "})
        recorded = self.cli("record", payload)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.assertEqual(json.loads(recorded.stdout)["entries"]["action:settings"]["count"], 1)
        loaded = self.cli("load")
        self.assertEqual(loaded.returncode, 0, loaded.stderr)
        self.assertEqual(json.loads(loaded.stdout), json.loads(recorded.stdout))
        reset = self.cli("reset")
        self.assertEqual(reset.returncode, 0, reset.stderr)
        self.assertEqual(json.loads(reset.stdout), history.defaults())

    def test_cli_concurrent_records_do_not_lose_choices(self):
        payload = json.dumps({"id": "app:kitty", "query": "ki"})
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.cli("record", payload), range(16)))
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
        item = history.load(self.state)["entries"]["app:kitty"]
        self.assertEqual(item["count"], 16)
        self.assertEqual(item["queries"]["ki"]["count"], 16)

    def test_cli_invalid_or_oversized_input_never_overwrites_history(self):
        history.record({"id": "app:kitty", "query": ""}, self.state)
        original = self.path.read_bytes()
        for payload in ("{broken", "null", " " * (history.MAX_REQUEST_BYTES + 1)):
            result = self.cli("record", payload)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(self.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
