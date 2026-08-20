from __future__ import annotations

import json
import unittest
from pathlib import Path

from wexp_ref.locks import validate_vectors_lock

ROOT = Path(__file__).resolve().parents[1]


class LockTests(unittest.TestCase):
    def test_checked_in_lock_is_exact_candidate_pin(self) -> None:
        value = json.loads((ROOT / "config/wexp-vectors.lock.json").read_text())
        result = validate_vectors_lock(value)
        self.assertEqual(result["status"], "VALID_PINNED_CANDIDATE")
        self.assertTrue(result["immutable_identity_available"])
        self.assertEqual(value["package_status"], "candidate")
        self.assertEqual(value["commit"], "cda36a36dcc1b66209e3781a26aa2a0d05e665ea")

    def test_exact_pinned_lock_is_ready(self) -> None:
        value = {
            "lock_version": 2,
            "dependency": "wexp-vectors",
            "repository": "WEXP-dev/wexp-vectors",
            "status": "pinned",
            "package_status": "candidate",
            "commit": "a" * 40,
            "manifest_path": "manifests/vectors.json",
            "manifest_sha256": "b" * 64,
        }
        result = validate_vectors_lock(value)
        self.assertEqual(result["status"], "VALID_PINNED_CANDIDATE")
        self.assertTrue(result["immutable_identity_available"])

    def test_execution_access_is_exact_candidate_pin(self) -> None:
        value = json.loads(
            (ROOT / "config/wexp-vectors-execution-access.json").read_text()
        )
        self.assertEqual(value["status"], "CANDIDATE_PINNED")
        self.assertEqual(value["commit"], "cda36a36dcc1b66209e3781a26aa2a0d05e665ea")

    def test_floating_ref_is_invalid(self) -> None:
        value = {
            "lock_version": 2,
            "dependency": "wexp-vectors",
            "repository": "WEXP-dev/wexp-vectors",
            "status": "pinned",
            "package_status": "candidate",
            "commit": "main",
            "manifest_path": "manifests/vectors.json",
            "manifest_sha256": "b" * 64,
        }
        self.assertEqual(validate_vectors_lock(value)["status"], "INVALID")

    def test_manifest_path_escape_is_invalid(self) -> None:
        value = json.loads((ROOT / "config/wexp-vectors.lock.json").read_text())
        value["manifest_path"] = "../vectors.json"
        self.assertEqual(validate_vectors_lock(value)["status"], "INVALID")

        value["manifest_path"] = "manifests\\vectors.json"
        self.assertEqual(validate_vectors_lock(value)["status"], "INVALID")

    def test_other_repository_is_invalid(self) -> None:
        value = json.loads((ROOT / "config/wexp-vectors.lock.json").read_text())
        value["repository"] = "example/other"
        self.assertEqual(validate_vectors_lock(value)["status"], "INVALID")


if __name__ == "__main__":
    unittest.main()
