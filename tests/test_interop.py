from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from wexp_ref.interop import InteropError, prepare_commitment, sha256_file, verify_reveal


class InteropTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.sources = self.root / "sources"
        self.sources.mkdir()
        (self.sources / "spec.txt").write_bytes(b"exact source bytes\n")
        self.lock = self.root / "source-lock.json"
        self.fixtures = self.root / "fixtures.bin"
        self.reading = self.root / "reading.json"
        self.fixtures.write_bytes(b"neutral fixtures\x00\x01")
        self.reading.write_bytes(b'{"result":"frozen"}\n')
        self._write_lock()

    def tearDown(self):
        self.tmp.cleanup()

    def _write_lock(self):
        value = {"artifact_version": "WEXP-INTEROP-SOURCE-LOCK-1", "repository": "example/protocol", "git_commit": "a" * 40, "materials": [{"path": "spec.txt", "sha256": sha256_file(self.sources / "spec.txt")}], "non_claims": ["Pinned source is not proof of semantic truth."]}
        self.lock.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")

    def test_exact_reading_bytes_are_load_bearing(self):
        commitment = prepare_commitment(self.lock, self.fixtures, self.reading)
        before = commitment["reading_sha256"]
        self.reading.write_bytes(b'{ "result": "frozen" }\n')
        self.assertNotEqual(before, sha256_file(self.reading))
        result = verify_reveal(commitment, self.lock, self.fixtures, self.reading, self.sources)
        self.assertEqual(result["status"], "COMMITMENT_MISMATCH")
        self.assertIn("reading_sha256", result["mismatches"])

    def test_selected_source_material_is_load_bearing(self):
        commitment = prepare_commitment(self.lock, self.fixtures, self.reading)
        (self.sources / "spec.txt").write_bytes(b"mutated\n")
        with self.assertRaises(InteropError):
            verify_reveal(commitment, self.lock, self.fixtures, self.reading, self.sources)

    def test_fixture_bytes_are_load_bearing(self):
        commitment = prepare_commitment(self.lock, self.fixtures, self.reading)
        self.fixtures.write_bytes(b"different fixtures")
        result = verify_reveal(commitment, self.lock, self.fixtures, self.reading, self.sources)
        self.assertEqual(result["status"], "COMMITMENT_MISMATCH")
        self.assertIn("fixtures_sha256", result["mismatches"])

    def test_verified_record_makes_no_semantic_comparison(self):
        commitment = prepare_commitment(self.lock, self.fixtures, self.reading)
        result = verify_reveal(commitment, self.lock, self.fixtures, self.reading, self.sources)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertNotIn("verdict", result)
        self.assertTrue(any("No semantic comparison" in item for item in result["non_claims"]))

    def test_source_lock_rejects_path_traversal(self):
        value = json.loads(self.lock.read_text())
        value["materials"][0]["path"] = "../spec.txt"
        self.lock.write_text(json.dumps(value) + "\n")
        with self.assertRaises(InteropError):
            prepare_commitment(self.lock, self.fixtures, self.reading)


if __name__ == "__main__":
    unittest.main()
