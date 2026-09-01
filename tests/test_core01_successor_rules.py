"""Successor position-4 families: scope/status consistency and non-Core token
resolution across applied registries.

These tests exercise both engines through the public engine protocol only, with
inputs shaped like the successor fixtures C14 and C17-C23. Expected outcomes are
stated from the specification text, never taken from an engine. The corpus
regressions at the end run only when the corresponding checkout is named by an
environment variable, and skip otherwise rather than passing silently.
"""

from __future__ import annotations

import copy
import itertools
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wexp_ref.core01.harness.engine import check_independence, load_engine  # noqa: E402
from wexp_ref.core01.harness.orchestrate import QUALIFIED, qualify  # noqa: E402

ENGINES = ("independent", "reference")

SCOPE_KEYS = [
    "carrier-mapping", "authenticity", "target-binding", "boundary-grounding",
    "observation-support", "intent-support", "invocation-support", "execution-support",
    "provenance-support", "independent-verification", "composition", "counter-evidence",
]

PROFILE = {
    "profile_version": 1,
    "profile_id": "successor-rules-test-profile",
    "semantics_version": "wexp-core-1",
    "representation": "successor-rules-test-harness",
    "harness": {"harness_schema_id": "urn:test", "label": "test", "vector_schema_id": "urn:test"},
    "scope_keys": SCOPE_KEYS,
    "status_domains": {
        "assessment": ["supported", "unsupported", "not-evaluated"],
        "boundary-grounding": ["asserted-only", "attributed", "attested", "not-evaluated"],
        "counter-evidence": ["not-supplied", "not-evaluated", "resolved-no-defeat",
                             "unresolved-material", "defeating"],
        "independence": ["supported", "unsupported", "not-evaluated", "not-applicable"],
    },
    "orderings": {"base": ["observation", "intent", "invocation", "execution"],
                  "qualifier": ["PROV", "IV"]},
    "qualifier_admissibility": {"PROV": ["execution"]},
    "qualifier_independence": {"IV": "supported", "PROV": "not-applicable"},
    "token_registry": {
        "classes": {
            "fatal": ["E_UNKNOWN_CRITICAL_SEMANTIC", "E_CLAIM_OUT_OF_DOMAIN", "E_PROFILE_MAPPING_INVALID"],
            "gap": ["E_IV_NOT_EVALUATED", "E_COUNTER_EVIDENCE_NOT_EVALUATED"],
            "substantive": ["E_BASE_EXCEEDS_BOUNDARY", "E_MISSING_REQUIRED_EVIDENCE",
                            "E_COUNTER_EVIDENCE_UNRESOLVED", "E_COUNTER_EVIDENCE_DEFEATING",
                            "P_COUNTER_FAIL"],
        },
        "derived_only": ["E_MALFORMED_NORMALIZED_INPUT", "E_UNSUPPORTED_SEMANTICS_VERSION",
                         "E_PROFILE_MAPPING_INVALID", "E_CLAIM_OUT_OF_DOMAIN"],
        "foreign_rejected": [],
        "roles": {
            "unknown_critical": "E_UNKNOWN_CRITICAL_SEMANTIC",
            "claim_out_of_domain": "E_CLAIM_OUT_OF_DOMAIN",
            "profile_mapping_invalid": "E_PROFILE_MAPPING_INVALID",
            "base_exceeds_boundary": "E_BASE_EXCEEDS_BOUNDARY",
            "missing_required_evidence": "E_MISSING_REQUIRED_EVIDENCE",
            "counter_evidence_unresolved": "E_COUNTER_EVIDENCE_UNRESOLVED",
            "counter_evidence_defeating": "E_COUNTER_EVIDENCE_DEFEATING",
            "counter_evidence_not_evaluated": "E_COUNTER_EVIDENCE_NOT_EVALUATED",
            "qualifier_not_evaluated": "E_IV_NOT_EVALUATED",
        },
    },
    "verdict_rules": {"precedence": ["fatal", "substantive", "default"],
                      "verdicts": {"fatal": "reject", "substantive": "downgrade", "default": "accept"}},
    "vector_bindings": {},
}

P1 = "urn:test:profile:P1:rev1"
P2 = "urn:test:profile:P2:rev1"
R1 = "urn:test:registry:R1"
R2 = "urn:test:registry:R2"
BIND_SUB = [{"token": "P_COUNTER_FAIL", "category": "substantive"}]
BIND_GAP = [{"token": "P_COUNTER_FAIL", "category": "evaluation-gap"}]


def scope(**overrides: str) -> dict[str, str]:
    value = {key: "evaluated" for key in SCOPE_KEYS}
    value.update(overrides)
    return value


def base_input() -> dict:
    return {
        "semantics_version": "wexp-core-1",
        "representation": "successor-rules-test-harness",
        "target": "T",
        "evaluation_context": {"id": "C"},
        "asserted_claim": {"base": "execution", "qualifiers": []},
        "boundary_finding": {"target": "T", "evaluation_context_ref": "C", "status": "supported",
                             "target_binding": "supported", "grounding": "attributed",
                             "ceiling_base": "execution", "basis_refs": ["bd"], "limitations": [],
                             "reasons": []},
        "base_findings": [{"base": "execution", "target": "T", "evaluation_context_ref": "C",
                           "target_binding": "supported", "semantic_validation": "supported",
                           "basis_refs": ["execution"], "limitations": [], "reasons": []}],
        "qualifier_findings": [],
        "counter_evidence": [{"status": "not-supplied", "affected_claims": [], "basis_refs": [],
                              "reasons": [], "limitations": []}],
        "profile_evaluation_gaps": [],
        "inherited_limitations": [],
        "recorder_relations": [],
        "fatal_conditions": [],
        "evaluation_scope": scope(),
    }


def c14_like(counter_scope: str) -> dict:
    value = base_input()
    value["counter_evidence"] = [
        {"status": "defeating", "affected_claims": [{"base": "intent", "qualifiers": []}],
         "basis_refs": [], "reasons": [], "limitations": []},
        {"status": "not-evaluated", "affected_claims": [{"base": "execution", "qualifiers": []}],
         "basis_refs": [], "reasons": [], "limitations": []},
    ]
    value["evaluation_scope"] = scope(**{"counter-evidence": counter_scope})
    return value


def c15_like(context: dict | None = None) -> dict:
    value = base_input()
    value["counter_evidence"] = [
        {"status": "unresolved-material", "affected_claims": [{"base": "execution", "qualifiers": []}],
         "basis_refs": ["p1"], "reasons": ["P_COUNTER_FAIL"], "limitations": []},
    ]
    if context is not None:
        value["evaluation_context"] = context
    return value


def registry(identity: str, bindings: list) -> dict:
    return {"identity": identity, "revision": "rev1", "bindings": copy.deepcopy(bindings)}


def context(profiles: list[str], references: list[tuple[str, dict]]) -> dict:
    return {
        "id": "C",
        "profile_identifiers": list(profiles),
        "registry_references": [{"referenced_by": p, "registry": r} for p, r in references],
    }


SUCCESSOR_ID = "draft-sergeev-wexp-core-successor-candidate-001"
PUBLISHED_ID = "draft-sergeev-wexp-core-01"


def run(engine_name: str, value: dict, profile: dict | None = None, snapshot_id: str = SUCCESSOR_ID) -> dict:
    engine = load_engine(engine_name)
    candidate = SimpleNamespace(profile=profile or PROFILE, snapshot_id=snapshot_id)
    vector = SimpleNamespace(vector_id="T-1", input=value)
    return engine.evaluate(vector, candidate)


def projection(result: dict) -> dict:
    return {k: v for k, v in result.items() if not k.startswith("diagnostic_")}


def is_profile_mapping_invalid(result: dict) -> bool:
    return result.get("verdict") == "reject" and result.get("fatal_reasons") == ["E_PROFILE_MAPPING_INVALID"]


class TestScopeStatusConsistency(unittest.TestCase):
    def test_evaluated_scope_with_governed_not_evaluated_counter_entry_is_fixed_rejection(self) -> None:
        # Successor fixture C17: the public C14 input.
        for name in ENGINES:
            with self.subTest(engine=name):
                result = run(name, c14_like("evaluated"))
                self.assertTrue(is_profile_mapping_invalid(result), result)

    def test_not_evaluated_scope_with_governed_not_evaluated_counter_entry_is_appraised(self) -> None:
        # Successor fixture C14 (repaired): the invariant is satisfied, so the
        # claim is appraised and the gap is emitted, not a rejection.
        for name in ENGINES:
            with self.subTest(engine=name):
                result = run(name, c14_like("not-evaluated"))
                self.assertEqual(result["verdict"], "downgrade")
                self.assertEqual(result["evaluation_gaps"], ["E_COUNTER_EVIDENCE_NOT_EVALUATED"])
                self.assertTrue(result["asserted_claim_supported"])

    def test_every_governed_family_is_screened(self) -> None:
        cases = {
            "base": lambda v: v["base_findings"][0].__setitem__("semantic_validation", "not-evaluated"),
            "target-binding": lambda v: v["base_findings"][0].__setitem__("target_binding", "not-evaluated"),
            "boundary": lambda v: v["boundary_finding"].update({"status": "not-evaluated", "grounding": "not-evaluated"}),
            "iv-independence": lambda v: v["qualifier_findings"].append(
                {"qualifier": "IV", "qualified_base": "execution", "target": "T",
                 "evaluation_context_ref": "C", "target_binding": "supported",
                 "semantic_validation": "supported", "independence_validation": "not-evaluated",
                 "basis_refs": ["iv"], "limitations": [], "reasons": []}),
        }
        for family, mutate in cases.items():
            for name in ENGINES:
                with self.subTest(engine=name, family=family):
                    value = base_input()
                    mutate(value)
                    self.assertTrue(is_profile_mapping_invalid(run(name, value)), family)

    def test_an_undeclared_capability_is_unconstrained(self) -> None:
        # A profile that does not declare counter-evidence in its scope cannot
        # be violated on that capability.
        value = c14_like("evaluated")
        value["evaluation_scope"].pop("counter-evidence")
        for name in ENGINES:
            with self.subTest(engine=name):
                self.assertEqual(run(name, value)["verdict"], "downgrade")


class TestNonCoreTokenResolution(unittest.TestCase):
    def test_zero_bindings_fail_closed(self) -> None:  # C18
        ctx = context([P1, P2], [(P1, registry(R1, [])), (P2, registry(R2, [{"token": "P_OTHER", "category": "substantive"}]))])
        for name in ENGINES:
            with self.subTest(engine=name):
                self.assertTrue(is_profile_mapping_invalid(run(name, c15_like(ctx))))

    def test_unique_binding_resolves_for_the_registry_reason(self) -> None:  # C19
        ctx = context([P1, P2], [(P1, registry(R1, BIND_SUB)), (P2, registry(R2, []))])
        for name in ENGINES:
            with self.subTest(engine=name):
                result = run(name, c15_like(ctx))
                self.assertEqual(result["verdict"], "downgrade")
                self.assertEqual(result["substantive_reasons"], ["E_COUNTER_EVIDENCE_UNRESOLVED", "P_COUNTER_FAIL"])
                ledger = result["diagnostic_token_resolution"]
                self.assertEqual(ledger["mode"], "multi-registry")
                self.assertEqual(ledger["tokens"]["P_COUNTER_FAIL"]["distinct_bindings"], 1)
                self.assertEqual(ledger["tokens"]["P_COUNTER_FAIL"]["bindings"], [f"{R1}@rev1:substantive"])

    def test_registry_binding_not_profile_registration_decides(self) -> None:
        # The profile still registers P_COUNTER_FAIL. Removing the registry
        # binding alone must flip the outcome: the pass in the previous test
        # rests on the registry reference, not on the profile.
        ctx = context([P1, P2], [(P1, registry(R1, [])), (P2, registry(R2, []))])
        for name in ENGINES:
            with self.subTest(engine=name):
                self.assertIn("P_COUNTER_FAIL", PROFILE["token_registry"]["classes"]["substantive"])
                self.assertTrue(is_profile_mapping_invalid(run(name, c15_like(ctx))))

    def test_two_distinct_bindings_fail_closed(self) -> None:  # C20
        ctx = context([P1, P2], [(P1, registry(R1, BIND_SUB)), (P2, registry(R2, BIND_SUB))])
        for name in ENGINES:
            with self.subTest(engine=name):
                self.assertTrue(is_profile_mapping_invalid(run(name, c15_like(ctx))))

    def test_resolution_is_order_independent(self) -> None:  # C21 and beyond
        references = [(P1, registry(R1, BIND_SUB)), (P2, registry(R2, BIND_SUB)),
                      ("urn:test:profile:P3:rev1", registry("urn:test:registry:R3", []))]
        profiles = [p for p, _ in references]
        for name in ENGINES:
            outcomes = set()
            for order in itertools.permutations(range(len(references))):
                ctx = context([profiles[i] for i in order], [references[i] for i in order])
                result = run(name, c15_like(ctx))
                outcomes.add((result["verdict"], tuple(result["fatal_reasons"])))
            with self.subTest(engine=name):
                self.assertEqual(outcomes, {("reject", ("E_PROFILE_MAPPING_INVALID",))})
        # And the positive case is order-independent too.
        references = [(P1, registry(R1, BIND_SUB)), (P2, registry(R2, []))]
        for name in ENGINES:
            seen = set()
            for order in itertools.permutations(range(2)):
                ctx = context([references[i][0] for i in order], [references[i] for i in order])
                result = projection(run(name, c15_like(ctx)))
                result.pop("evaluation_context")  # carried verbatim, so it differs by order
                seen.add(repr(sorted(result.items())))
            with self.subTest(engine=name):
                self.assertEqual(len(seen), 1)

    def test_category_mismatch_fails_closed(self) -> None:  # C22
        ctx = context([P1, P2], [(P1, registry(R1, BIND_GAP)), (P2, registry(R2, []))])
        for name in ENGINES:
            with self.subTest(engine=name):
                self.assertTrue(is_profile_mapping_invalid(run(name, c15_like(ctx))))

    def test_byte_identical_duplicate_references_deduplicate(self) -> None:  # C23
        ctx = context([P1, P2], [(P1, registry(R1, BIND_SUB)), (P2, registry(R1, BIND_SUB))])
        for name in ENGINES:
            with self.subTest(engine=name):
                result = run(name, c15_like(ctx))
                self.assertEqual(result["verdict"], "downgrade")
                self.assertEqual(result["diagnostic_token_resolution"]["distinct_registries"], 1)

    def test_a_non_identical_duplicate_stays_distinct(self) -> None:
        # Same identity and revision but different bytes: not byte-identical,
        # therefore two distinct bindings, therefore fail closed.
        other = registry(R1, BIND_SUB)
        other["bindings"].append({"token": "P_OTHER", "category": "substantive"})
        ctx = context([P1, P2], [(P1, registry(R1, BIND_SUB)), (P2, other)])
        for name in ENGINES:
            with self.subTest(engine=name):
                self.assertTrue(is_profile_mapping_invalid(run(name, c15_like(ctx))))

    def test_core_tokens_are_not_resolved_through_registries(self) -> None:
        # A Core gap token supplied in profile_evaluation_gaps binds to the
        # semantics version, not to an applied registry.
        ctx = context([P1], [(P1, registry(R1, []))])
        value = base_input()
        value["evaluation_context"] = ctx
        value["profile_evaluation_gaps"] = [{"token": "E_IV_NOT_EVALUATED", "target": "T",
                                            "evaluation_context_ref": "C",
                                            "affected_claims": [{"base": "execution", "qualifiers": []}],
                                            "basis_refs": ["u1"], "limitations": []}]
        for name in ENGINES:
            with self.subTest(engine=name):
                result = run(name, value)
                self.assertEqual(result["verdict"], "accept")
                self.assertEqual(result["evaluation_gaps"], ["E_IV_NOT_EVALUATED"])

    def test_reference_by_a_profile_outside_the_applied_set_fails_closed(self) -> None:
        ctx = context([P1], [(P2, registry(R1, BIND_SUB))])
        for name in ENGINES:
            with self.subTest(engine=name):
                self.assertTrue(is_profile_mapping_invalid(run(name, c15_like(ctx))))

    def test_without_registry_references_the_profile_registry_is_the_single_applied_registry(self) -> None:
        for name in ENGINES:
            with self.subTest(engine=name):
                result = run(name, c15_like())
                self.assertEqual(result["verdict"], "downgrade")
                self.assertEqual(result["diagnostic_token_resolution"]["mode"], "single-applied-registry")
                # Under the published identity the predecessor result carries no ledger at all.
                self.assertNotIn("diagnostic_token_resolution", run(name, c15_like(), snapshot_id=PUBLISHED_ID))


class TestContractIdentityBinding(unittest.TestCase):
    """The successor families are keyed on the contract identity being appraised.

    The published Core-01 object's normative fixture C14 contradicts its own
    scope-consistency text (WCR2V-001 known issue C1). An engine that must
    reproduce the published fixture table under the published identity and the
    repaired table under the successor identity cannot apply the invariant to
    both, so the families switch on ``candidate.snapshot_id``.
    """

    def test_the_published_identity_keeps_the_predecessor_screen(self) -> None:
        for name in ENGINES:
            with self.subTest(engine=name):
                result = run(name, c14_like("evaluated"), snapshot_id=PUBLISHED_ID)
                self.assertEqual(result["verdict"], "downgrade")
                self.assertEqual(result["evaluation_gaps"], ["E_COUNTER_EVIDENCE_NOT_EVALUATED"])
                ctx = context([P1, P2], [(P1, registry(R1, BIND_SUB)), (P2, registry(R2, BIND_SUB))])
                self.assertEqual(run(name, c15_like(ctx), snapshot_id=PUBLISHED_ID)["verdict"], "downgrade")

    def test_the_successor_identity_applies_both_families(self) -> None:
        for name in ENGINES:
            with self.subTest(engine=name):
                self.assertTrue(is_profile_mapping_invalid(run(name, c14_like("evaluated"), snapshot_id=SUCCESSOR_ID)))
                ctx = context([P1, P2], [(P1, registry(R1, BIND_SUB)), (P2, registry(R2, BIND_SUB))])
                self.assertTrue(is_profile_mapping_invalid(run(name, c15_like(ctx), snapshot_id=SUCCESSOR_ID)))


class TestEnginesAgree(unittest.TestCase):
    def test_both_engines_project_identically_on_every_case(self) -> None:
        cases = [c14_like("evaluated"), c14_like("not-evaluated"), c15_like(),
                 c15_like(context([P1, P2], [(P1, registry(R1, BIND_SUB)), (P2, registry(R2, []))])),
                 c15_like(context([P1, P2], [(P1, registry(R1, BIND_SUB)), (P2, registry(R2, BIND_SUB))])),
                 c15_like(context([P1, P2], [(P1, registry(R1, BIND_GAP)), (P2, registry(R2, []))])),
                 c15_like(context([P1, P2], [(P1, registry(R1, BIND_SUB)), (P2, registry(R1, BIND_SUB))]))]
        for index, value in enumerate(cases):
            with self.subTest(case=index):
                self.assertEqual(projection(run("independent", value)), projection(run("reference", value)))

    def test_the_firewall_still_holds(self) -> None:
        self.assertEqual(check_independence(), [])


class TestCorpusRegression(unittest.TestCase):
    def _qualify(self, variable: str, expected_vectors: int) -> None:
        corpus = os.environ.get(variable)
        if not corpus:
            self.skipTest(f"{variable} not set")
        with tempfile.TemporaryDirectory() as tmp:
            outcome = qualify(Path(corpus), Path(tmp), environment_label="portable")
        summary = outcome.bundle["comparison"]["summary"]
        self.assertEqual(outcome.status, QUALIFIED, summary)
        self.assertEqual(summary["vectors"], expected_vectors)
        self.assertEqual(summary["agree"], expected_vectors)
        self.assertEqual(summary["expected_mismatch"], 0)

    def test_public_set_001_still_qualifies(self) -> None:
        self._qualify("WEXP_CORE01_CORPUS", 16)

    def test_frozen_successor_set_qualifies(self) -> None:
        self._qualify("WEXP_CORE01_SUCCESSOR_CORPUS", 23)


if __name__ == "__main__":
    unittest.main()
