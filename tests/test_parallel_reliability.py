"""Isolated regressions from the parallel desktop reliability review."""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from sumi import operations, profiles


class ReceiptReconciliationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sumi-receipt-reliability-")
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name)
        self.receipt = operations.create(["profile", "use", "sumi"], self.state)
        self.receipt.update(status="running", updated_at="2020-01-01T00:00:00+00:00")
        profiles._json(self.state / "operations" / (self.receipt["id"] + ".json"), self.receipt)

    def reconcile_after_another_writer_wins(self, **changes):
        """Finish a writer after the initial read, before reconciliation locks."""
        original_flock = fcntl.flock
        winner = []

        def acquire(lock, mode):
            # A controller that held this lock can finish immediately before
            # reconciliation acquires it. No sleeping or thread timing needed.
            if not winner:
                winner.append(operations.update(self.receipt["id"], self.state, **changes))
            return original_flock(lock, mode)

        inactive = subprocess.CompletedProcess([], 0, "ActiveState=inactive\nLoadState=not-found\n", "")
        with patch.dict(os.environ, {"SUMI_DRY_RUN": "0"}), \
                patch.object(operations.fcntl, "flock", side_effect=acquire), \
                patch.object(profiles, "_run", return_value=inactive) as probe:
            result = operations.status(self.receipt["id"], self.state)
        self.assertEqual(len(winner), 1)
        return result, winner[0], probe

    def test_completion_between_receipt_read_and_lock_is_not_overwritten_as_failed(self):
        result, winner, probe = self.reconcile_after_another_writer_wins(
            status="succeeded", result={"profile": "sumi"}, exit_code=0)
        self.assertEqual(result, winner)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(operations.status(self.receipt["id"], self.state, reconcile=False), winner)
        probe.assert_not_called()

    def test_recent_running_rewrite_gets_its_own_startup_grace_period(self):
        result, winner, probe = self.reconcile_after_another_writer_wins(status="running", pid=1234)
        self.assertEqual(result, winner)
        self.assertEqual(result["status"], "running")
        self.assertEqual(operations.status(self.receipt["id"], self.state, reconcile=False), winner)
        probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
