"""Section 8.6 present-aggregate status rows: E_EVIDENCE_NOT_BOUND and
E_EXACT_CLAIM_NOT_SUPPORTED.

Both rows are optional vocabulary: they fire only when the profile registers a
token for the role (``evidence_not_bound`` / ``exact_claim_not_supported``).
Under a profile that does not register them the predecessor behaviour stands
(the claim collapses onto missing-required-evidence), which is what keeps the
frozen public and successor results byte-identical. Expected outcomes below are
stated from the specification text, never taken from an engine.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wexp_ref.core01.harness.engine import check_independence, load_engine  # noqa: E402

from tests.test_core01_successor_rules import PROFILE, SUCCESSOR_ID, base_input, projection  # noqa: E402

ENGINES = ("independent", "reference")

ROW_PROFILE = copy.deepcopy(PROFILE)
ROW_PROFILE["profile_id"] = "matrix-rows-test-profile"
ROW_PROFILE["token_registry"]["classes"]["substantive"] += ["E_EVIDENCE_NOT_BOUND", "E_EXACT_CLAIM_NOT_SUPPORTED"]
ROW_PROFILE["token_registry"]["roles"]["evidence_not_bound"] = "E_EVIDENCE_NOT_BOUND"
ROW_PROFILE["token_registry"]["roles"]["exact_claim_not_supported"] = "E_EXACT_CLAIM_NOT_SUPPORTED"


def run(engine_name: str, value: dict, profile: dict) -> dict:
    engine = load_engine(engine_name)
    candidate = SimpleNamespace(profile=profile, snapshot_id=SUCCESSOR_ID)
    return engine.evaluate(SimpleNamespace(vector_id="T-1", input=value), candidate)


def with_execution(target_binding: str, semantic_validation: str) -> dict:
    value = base_input()
    value["base_findings"][0]["target_binding"] = target_binding
    value["base_findings"][0]["semantic_validation"] = semantic_validation
    return value


class TestExactClaimNotSupportedRow(unittest.TestCase):
    def test_present_asserted_base_with_unsupported_semantics_names_the_row(self) -> None:
        for name in ENGINES:
            with self.subTest(engine=name):
                result = run(name, with_execution("supported", "unsupported"), ROW_PROFILE)
                self.assertEqual(result["verdict"], "downgrade")
                self.assertFalse(result["asserted_claim_supported"])
                self.assertEqual(result["substantive_reasons"], ["E_EXACT_CLAIM_NOT_SUPPORTED"])
                self.assertEqual(result["supported_claims"], [])

    def test_without_the_registered_token_the_claim_collapses_as_before(self) -> None:
        for name in ENGINES:
            with self.subTest(engine=name):
                result = run(name, with_execution("supported", "unsupported"), PROFILE)
                self.assertEqual(result["substantive_reasons"], ["E_MISSING_REQUIRED_EVIDENCE"])

    def test_an_absent_aggregate_still_triggers_only_its_absence_row(self) -> None:
        value = base_input()
        value["base_findings"] = []
        for name in ENGINES:
            with self.subTest(engine=name):
                result = run(name, value, ROW_PROFILE)
                self.assertEqual(result["substantive_reasons"], ["E_MISSING_REQUIRED_EVIDENCE"])


class TestEvidenceNotBoundRow(unittest.TestCase):
    def test_present_asserted_base_with_unsupported_binding_names_the_row(self) -> None:
        for name in ENGINES:
            with self.subTest(engine=name):
                result = run(name, with_execution("unsupported", "supported"), ROW_PROFILE)
                self.assertEqual(result["verdict"], "downgrade")
                self.assertEqual(result["substantive_reasons"], ["E_EVIDENCE_NOT_BOUND"])

    def test_both_rows_fire_together_when_both_apply(self) -> None:
        for name in ENGINES:
            with self.subTest(engine=name):
                result = run(name, with_execution("unsupported", "unsupported"), ROW_PROFILE)
                self.assertEqual(result["substantive_reasons"],
                                 ["E_EVIDENCE_NOT_BOUND", "E_EXACT_CLAIM_NOT_SUPPORTED"])

    def test_asserted_qualifier_with_unsupported_binding_names_the_row(self) -> None:
        value = base_input()
        value["asserted_claim"] = {"base": "execution", "qualifiers": ["IV"]}
        value["qualifier_findings"] = [{
            "qualifier": "IV", "qualified_base": "execution", "target": "T",
            "evaluation_context_ref": "C", "target_binding": "unsupported",
            "semantic_validation": "supported", "independence_validation": "supported",
            "basis_refs": ["iv"], "limitations": [], "reasons": []}]
        for name in ENGINES:
            with self.subTest(engine=name):
                result = run(name, value, ROW_PROFILE)
                self.assertEqual(result["verdict"], "downgrade")
                self.assertEqual(result["substantive_reasons"], ["E_EVIDENCE_NOT_BOUND"])
                # The bare execution claim remains supported; only the IV claim fails.
                self.assertEqual(result["supported_claims"], [{"base": "execution", "qualifiers": []}])

    def test_a_supported_aggregate_produces_no_row(self) -> None:
        for name in ENGINES:
            with self.subTest(engine=name):
                result = run(name, with_execution("supported", "supported"), ROW_PROFILE)
                self.assertEqual(result["verdict"], "accept")
                self.assertEqual(result["substantive_reasons"], [])


class TestAgreementAndFirewall(unittest.TestCase):
    def test_both_engines_project_identically(self) -> None:
        cases = [with_execution("supported", "unsupported"), with_execution("unsupported", "supported"),
                 with_execution("unsupported", "unsupported"), with_execution("supported", "supported")]
        for index, value in enumerate(cases):
            for profile in (ROW_PROFILE, PROFILE):
                with self.subTest(case=index, profile=profile["profile_id"]):
                    self.assertEqual(projection(run("independent", value, profile)),
                                     projection(run("reference", value, profile)))

    def test_the_firewall_still_holds(self) -> None:
        self.assertEqual(check_independence(), [])


if __name__ == "__main__":
    unittest.main()
