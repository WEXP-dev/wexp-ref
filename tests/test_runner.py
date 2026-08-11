from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from wexp_ref.runner import PlanError, run_plan
from wexp_ref.runner.executor import REQUIRED_NON_CLAIMS


def plan() -> dict:
    return {
        "plan_version": 1,
        "execution_id": "test-run",
        "subject": "test declared execution",
        "source": {
            "repository": "local:test",
            "revision": "a" * 40,
            "revision_status": "pinned",
        },
        "dependencies": [],
        "external_dependencies": [],
        "inputs": [{"path": "input.txt"}],
        "procedure": [
            {
                "name": "copy",
                "argv": [
                    "{python}",
                    "-c",
                    "from pathlib import Path; Path('output.txt').write_bytes(Path('input.txt').read_bytes())",
                ],
            }
        ],
        "outputs": [{"artifact": "output.txt", "required": True}],
        "claims": ["declared command observed"],
        "non_claims": [],
    }


class RunnerTests(unittest.TestCase):
    def test_runner_hashes_inputs_outputs_and_never_uses_shell(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.joinpath("input.txt").write_text("evidence", encoding="utf-8")
            record = run_plan(plan(), root)
        digest = hashlib.sha256(b"evidence").hexdigest()
        self.assertEqual(record["overall_exit_status"], 0)
        self.assertEqual(record["record_kind"], "wexp-ref-runner-observation")
        self.assertEqual(record["source"]["input_hashes"][0]["sha256"], digest)
        self.assertEqual(record["outputs"][0]["sha256"], digest)
        self.assertFalse(record["observations"][0]["shell"])
        for statement in REQUIRED_NON_CLAIMS:
            self.assertIn(statement, record["non_claims"])

    def test_input_hash_mismatch_prevents_execution(self) -> None:
        value = plan()
        value["inputs"][0]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.joinpath("input.txt").write_text("different", encoding="utf-8")
            record = run_plan(value, root)
        self.assertEqual(record["overall_exit_status"], 1)
        self.assertEqual(record["observations"][0]["status"], "NOT_RUN")

    def test_workspace_escape_is_rejected(self) -> None:
        value = plan()
        value["inputs"][0]["path"] = "../secret"
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(PlanError):
                run_plan(value, temporary)

    def test_floating_source_revision_is_rejected(self) -> None:
        value = plan()
        value["source"]["revision"] = "HEAD"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.joinpath("input.txt").write_text("x")
            with self.assertRaises(PlanError):
                run_plan(value, root)

    def test_nonzero_command_is_observed(self) -> None:
        value = plan()
        value["procedure"][0]["argv"] = ["{python}", "-c", "raise SystemExit(7)"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.joinpath("input.txt").write_text("x")
            record = run_plan(value, root)
        self.assertEqual(record["exit_statuses"]["copy"], 7)
        self.assertEqual(record["overall_exit_status"], 1)
        self.assertEqual(record["outputs"][0]["status"], "MISSING")


if __name__ == "__main__":
    unittest.main()
