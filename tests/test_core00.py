from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from wexp_ref.core00 import Core00InputError, PackageError, evaluate, run_package
from wexp_ref.cli import main as cli_main

CORE_XML_SHA256 = "6cd8b680059cc81e1ec4c84737d9319ee242ef63e89c57de497bd57ede08d810"


def harness_input() -> dict:
    return {
        "prior_checks": {
            "structure": "valid",
            "canonicalization": "valid",
            "timestamps": "valid",
            "signature": "valid",
            "key_binding": "valid",
            "capabilities_resolution": "accepted",
            "hash_algorithms": "supported",
            "recorder_qualification": "absent",
            "chain": "absent",
        },
        "boundary_type": "proxy",
        "claimed_level": "WL2",
        "effective_conformance_class": "CC2",
        "evidence": {
            "arguments_hash": True,
            "execution_fields": False,
            "bound_provenance": False,
            "bound_independent_verification": False,
        },
        "unknown_extensions": [],
    }


def vector(value: dict | None = None) -> dict:
    input_value = value if value is not None else harness_input()
    return {
        "vector_id": "WEXP-CORE-00-V9001",
        "specification": {
            "document": "draft-sergeev-wexp-core",
            "revision": "00",
            "artifact": "xml",
            "sha256": CORE_XML_SHA256,
        },
        "requirement_ids": ["WEXP-CORE-00-REQ-0006"],
        "purpose": "Exercise a test-local package fixture.",
        "classification": "positive",
        "test_representation": {
            "id": "wexp-core-00-test-harness",
            "revision": "1",
            "status": "non-normative-test-representation",
        },
        "input": input_value,
        "expected": {"verdict": "accept", "verified_level": "WL2"},
        "derivation": {"source_locators": ["test"], "steps": ["test"]},
    }


def write_json(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    path.write_text(rendered, encoding="utf-8")
    return hashlib.sha256(rendered.encode()).hexdigest()


def package(root: Path, item: dict | None = None) -> dict:
    vector_value = item if item is not None else vector()
    vector_path = root / "vectors/core-00/WEXP-CORE-00-V9001.json"
    vector_hash = write_json(vector_path, vector_value)
    manifest = {
        "manifest_version": 2,
        "manifest_kind": "wexp-vector-integrity-index",
        "repository_version": "test",
        "release_status": "candidate",
        "vector_category": "specification-derived-test-vectors",
        "schemas": {},
        "requirements": {},
        "vectors": [
            {
                "path": "vectors/core-00/WEXP-CORE-00-V9001.json",
                "vector_id": "WEXP-CORE-00-V9001",
                "classification": vector_value["classification"],
                "status": "candidate",
                "sha256": vector_hash,
            }
        ],
    }
    manifest_hash = write_json(root / "manifests/vectors.json", manifest)
    return {
        "lock_version": 2,
        "dependency": "wexp-vectors",
        "repository": "WEXP-dev/wexp-vectors",
        "status": "pinned",
        "package_status": "candidate",
        "commit": "a" * 40,
        "manifest_path": "manifests/vectors.json",
        "manifest_sha256": manifest_hash,
    }


class EvaluatorTests(unittest.TestCase):
    def test_direct_supported_case(self) -> None:
        self.assertEqual(
            evaluate(harness_input()),
            {"verdict": "accept", "verified_level": "WL2"},
        )

    def test_manual_approval_boundary_downgrades(self) -> None:
        value = harness_input()
        value["boundary_type"] = "manual-approval"
        self.assertEqual(
            evaluate(value),
            {"verdict": "downgrade", "verified_level": "WL1"},
        )

    def test_capability_ceiling_downgrades_wl4(self) -> None:
        value = harness_input()
        value.update(
            boundary_type="host-hook",
            claimed_level="WL4",
            effective_conformance_class="CC3",
        )
        value["evidence"].update(execution_fields=True, bound_provenance=True)
        self.assertEqual(
            evaluate(value),
            {"verdict": "downgrade", "verified_level": "WL3"},
        )

    def test_independent_verification_does_not_substitute_for_wl4_provenance(self) -> None:
        value = harness_input()
        value.update(
            boundary_type="host-hook",
            claimed_level="WL4",
            effective_conformance_class="CC5",
        )
        value["evidence"].update(
            execution_fields=True,
            bound_independent_verification=True,
        )
        self.assertEqual(
            evaluate(value),
            {"verdict": "downgrade", "verified_level": "WL3"},
        )

    def test_missing_wl5_evidence_downgrades_to_wl4(self) -> None:
        value = harness_input()
        value.update(
            boundary_type="host-hook",
            claimed_level="WL5",
            effective_conformance_class="CC5",
        )
        value["evidence"].update(execution_fields=True, bound_provenance=True)
        self.assertEqual(
            evaluate(value),
            {"verdict": "downgrade", "verified_level": "WL4"},
        )

    def test_missing_execution_fields_downgrades_to_wl2(self) -> None:
        value = harness_input()
        value.update(
            boundary_type="host-hook",
            claimed_level="WL3",
            effective_conformance_class="CC3",
        )
        self.assertEqual(
            evaluate(value),
            {"verdict": "downgrade", "verified_level": "WL2"},
        )

    def test_higher_level_fields_do_not_satisfy_lower_claim_fields(self) -> None:
        for claimed_level in ("WL1", "WL2"):
            with self.subTest(claimed_level=claimed_level):
                value = harness_input()
                value.update(
                    boundary_type="host-hook",
                    claimed_level=claimed_level,
                    effective_conformance_class="CC5",
                )
                value["evidence"].update(
                    arguments_hash=False,
                    execution_fields=True,
                )
                self.assertEqual(
                    evaluate(value),
                    {"verdict": "downgrade", "verified_level": "WL0"},
                )

    def test_unknown_critical_extension_rejects_before_level_evaluation(self) -> None:
        value = harness_input()
        value["unknown_extensions"] = [{"name": "slice-unknown", "critical": True}]
        self.assertEqual(
            evaluate(value),
            {"verdict": "reject", "errors": ["E_UNKNOWN_CRITICAL_EXTENSION"]},
        )

    def test_extension_names_must_be_unique(self) -> None:
        value = harness_input()
        value["unknown_extensions"] = [
            {"name": "slice-unknown", "critical": False},
            {"name": "slice-unknown", "critical": True},
        ]
        with self.assertRaisesRegex(Core00InputError, "unique names"):
            evaluate(value)

    def test_unknown_input_member_is_rejected(self) -> None:
        value = harness_input()
        value["future"] = True
        with self.assertRaises(Core00InputError):
            evaluate(value)

    def test_out_of_slice_boundary_is_rejected(self) -> None:
        value = harness_input()
        value["boundary_type"] = "kernel"
        with self.assertRaisesRegex(Core00InputError, "outside the first slice"):
            evaluate(value)

    def test_integer_is_not_accepted_as_boolean(self) -> None:
        value = harness_input()
        value["evidence"]["arguments_hash"] = 1
        with self.assertRaisesRegex(Core00InputError, "must be a boolean"):
            evaluate(value)

    def test_non_string_scalar_fields_fail_cleanly(self) -> None:
        for field in ("boundary_type", "effective_conformance_class"):
            with self.subTest(field=field):
                value = harness_input()
                value[field] = []
                with self.assertRaises(Core00InputError):
                    evaluate(value)


class PackageTests(unittest.TestCase):
    def test_candidate_package_is_deterministic_and_agrees(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = package(root)
            first = run_package(root, lock)
            second = run_package(root, deepcopy(lock))
        self.assertEqual(first, second)
        self.assertEqual(
            first["summary"],
            {"total": 1, "agree": 1, "disagree": 0, "status": "PASS"},
        )
        self.assertEqual(first["vector_package"]["package_status"], "candidate")

    def test_manifest_digest_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = package(root)
            lock["manifest_sha256"] = "0" * 64
            with self.assertRaisesRegex(PackageError, "manifest SHA-256"):
                run_package(root, lock)

    def test_expected_result_mismatch_is_observed_not_rewritten(self) -> None:
        item = vector()
        item["expected"] = {"verdict": "downgrade", "verified_level": "WL1"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = run_package(root, package(root, item))
        self.assertEqual(result["summary"]["status"], "FAIL")
        self.assertEqual(result["results"][0]["result"], "DISAGREE")

    def test_duplicate_manifest_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = package(root)
            path = root / "manifests/vectors.json"
            path.write_text(
                '{"manifest_version":2,"manifest_version":2}', encoding="utf-8"
            )
            lock["manifest_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(PackageError, "duplicate JSON member"):
                run_package(root, lock)

    def test_duplicate_vector_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = package(root)
            path = root / "vectors/core-00/WEXP-CORE-00-V9001.json"
            rendered = path.read_text(encoding="utf-8")
            duplicate = rendered.replace(
                '  "vector_id": "WEXP-CORE-00-V9001"',
                '  "vector_id": "WEXP-CORE-00-V9001",\n  "vector_id": "WEXP-CORE-00-V9001"',
                1,
            )
            path.write_text(duplicate, encoding="utf-8")
            manifest_path = root / "manifests/vectors.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["vectors"][0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            lock["manifest_sha256"] = write_json(manifest_path, manifest)
            with self.assertRaisesRegex(PackageError, "duplicate JSON member"):
                run_package(root, lock)

    def test_symlinked_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = package(root)
            manifest = root / "manifests/vectors.json"
            target = root / "manifest-target.json"
            manifest.replace(target)
            try:
                manifest.symlink_to(target)
            except OSError as exc:  # pragma: no cover - platform dependent
                self.skipTest(f"symbolic links unavailable: {exc}")
            with self.assertRaisesRegex(PackageError, "symbolic link"):
                run_package(root, lock)

    def test_unhashable_requirement_id_is_rejected_cleanly(self) -> None:
        item = vector()
        item["requirement_ids"] = [[]]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(PackageError, "invalid requirement_ids"):
                run_package(root, package(root, item))

    def test_package_cli_reports_malformed_vector_without_traceback(self) -> None:
        item = vector()
        item["requirement_ids"] = [[]]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock_path = root / "lock.json"
            write_json(lock_path, package(root, item))
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = cli_main(
                    ["core00-run-vectors", str(root), "--lock", str(lock_path)]
                )
        self.assertEqual(2, status)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("Core -00 package error:", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
