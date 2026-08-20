"""Windows checkout diagnostics remain strict and fail closed."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "WEXP-SYNTH-CANDIDATE-A"
sys.path.insert(0, str(ROOT / "src"))

from wexp_ref.core01.harness import canonical, orchestrate  # noqa: E402
from wexp_ref.core01.harness.candidate import (  # noqa: E402
    LINE_ENDING_MISMATCH_HINT,
    CandidateError,
    load,
)


class TestLineEndingMismatchDiagnostic(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / FIXTURE.name
        shutil.copytree(FIXTURE, self.root)

    @staticmethod
    def _to_crlf(path: Path) -> None:
        raw = path.read_bytes()
        if b"\r\n" in raw or b"\n" not in raw:
            raise AssertionError(f"test input must contain LF-only line endings: {path}")
        path.write_bytes(raw.replace(b"\n", b"\r\n"))

    def _load_error(self) -> str:
        with self.assertRaises(CandidateError) as caught:
            load(self.root)
        return str(caught.exception)

    def test_helper_detects_both_lf_crlf_directions_from_the_existing_buffer(self) -> None:
        lf = b"alpha\nbeta\n"
        crlf = b"alpha\r\nbeta\r\n"
        lf_artifact = canonical.Artifact(
            path=Path("lf.txt"), raw=lf, sha256=hashlib.sha256(lf).hexdigest()
        )
        crlf_artifact = canonical.Artifact(
            path=Path("crlf.txt"), raw=crlf, sha256=hashlib.sha256(crlf).hexdigest()
        )

        self.assertTrue(
            canonical.is_line_ending_only_mismatch(
                lf_artifact, hashlib.sha256(crlf).hexdigest()
            )
        )
        self.assertTrue(
            canonical.is_line_ending_only_mismatch(
                crlf_artifact, hashlib.sha256(lf).hexdigest()
            )
        )

    def test_helper_refuses_generic_binary_and_nul_mismatches(self) -> None:
        declared = hashlib.sha256(b"alpha\nbeta\n").hexdigest()
        for raw in (b"alpha\nchanged\n", b"alpha\xff\n", b"alpha\x00\r\n"):
            artifact = canonical.Artifact(
                path=Path("observed"), raw=raw, sha256=hashlib.sha256(raw).hexdigest()
            )
            self.assertFalse(canonical.is_line_ending_only_mismatch(artifact, declared))

    def test_profile_crlf_mismatch_gets_hint_and_stays_rejected(self) -> None:
        self._to_crlf(self.root / "profile.json")

        message = self._load_error()

        self.assertIn("profile digest mismatch", message)
        self.assertIn(LINE_ENDING_MISMATCH_HINT, message)

    def test_bundled_specification_crlf_mismatch_gets_hint_and_stays_rejected(self) -> None:
        spec = self.root / "spec" / "core.xml"
        spec.parent.mkdir()
        canonical_raw = b"<spec>\n  <section/>\n</spec>\n"
        spec.write_bytes(canonical_raw)
        descriptor_path = self.root / "descriptor.json"
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        descriptor["authority"] = {
            "published_specification": True,
            "snapshot_id": "WEXP-SYNTH-SNAPSHOT-A",
            "snapshot_path": "spec/core.xml",
            "xml_bytes": len(canonical_raw),
            "xml_sha256": hashlib.sha256(canonical_raw).hexdigest(),
        }
        descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")
        self._to_crlf(spec)

        message = self._load_error()

        self.assertIn("bundled specification does not match", message)
        self.assertIn(LINE_ENDING_MISMATCH_HINT, message)

    def test_bound_file_crlf_mismatch_gets_hint_and_stays_rejected(self) -> None:
        target = sorted((self.root / "vectors").glob("*.json"))[0]
        self._to_crlf(target)

        message = self._load_error()

        self.assertIn("bound_files: SHA-256 mismatch", message)
        self.assertIn(LINE_ENDING_MISMATCH_HINT, message)

    def test_generic_one_byte_mismatch_has_no_line_ending_hint(self) -> None:
        target = sorted((self.root / "vectors").glob("*.json"))[0]
        raw = bytearray(target.read_bytes())
        raw[0] ^= 1
        target.write_bytes(raw)

        message = self._load_error()

        self.assertIn("bound_files: SHA-256 mismatch", message)
        self.assertNotIn("line-ending normalization", message)

    def test_cli_reports_fail_and_exit_one_for_line_ending_only_mismatch(self) -> None:
        self._to_crlf(self.root / "profile.json")
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            status = orchestrate.main(
                [
                    "--candidate",
                    str(self.root),
                    "--output",
                    str(Path(self._tmp.name) / "qualification"),
                ]
            )

        self.assertEqual(status, 1)
        self.assertIn(orchestrate.NOT_QUALIFIED, stderr.getvalue())
        self.assertIn(LINE_ENDING_MISMATCH_HINT, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
