from __future__ import annotations

import json
import unittest
from pathlib import Path

from wexp_ref.locks import validate_vectors_lock

ROOT = Path(__file__).resolve().parents[1]


class LockTests(unittest.TestCase):
    def test_checked_in_lock_is_explicitly_blocked(self) -> None:
        value = json.loads((ROOT / "config/wexp-vectors.lock.json").read_text())
        result = validate_vectors_lock(value)
        self.assertEqual(result["status"], "VALID_BLOCKED")
        self.assertFalse(result["immutable_identity_available"])
        self.assertNotIn("commit", value)
        self.assertNotIn("manifest_sha256", value)

    def test_exact_pinned_lock_is_ready(self) -> None:
        value = {
            "lock_version": 1,
            "dependency": "wexp-vectors",
            "repository": "WEXP-dev/wexp-vectors",
            "status": "pinned",
            "commit": "a" * 40,
            "manifest_sha256": "b" * 64,
        }
        result = validate_vectors_lock(value)
        self.assertEqual(result["status"], "VALID_PINNED")
        self.assertTrue(result["immutable_identity_available"])

    def test_execution_access_is_separately_blocked(self) -> None:
        value = json.loads(
            (ROOT / "config/wexp-vectors-execution-access.json").read_text()
        )
        self.assertEqual(value["status"], "BLOCKED")
        self.assertNotIn("pinned_commit", value)

    def test_floating_ref_is_invalid(self) -> None:
        value = {
            "lock_version": 1,
            "dependency": "wexp-vectors",
            "repository": "WEXP-dev/wexp-vectors",
            "status": "blocked",
            "blocked_reason": "main",
            "required_resolution": "pin it",
        }
        self.assertEqual(validate_vectors_lock(value)["status"], "INVALID")


if __name__ == "__main__":
    unittest.main()
