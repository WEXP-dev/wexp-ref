"""Tests for the generic qualification pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "wexp_ref" / "core01"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(ROOT / "src"))

from wexp_ref.core01.harness import canonical, schema as schema_module  # noqa: E402
from wexp_ref.core01.harness.candidate import CandidateError, load, token_for  # noqa: E402
from wexp_ref.core01.harness.engine import check_independence, load_engine  # noqa: E402
from wexp_ref.core01.harness.orchestrate import QUALIFIED, qualify  # noqa: E402
from wexp_ref.core01.tools import new_candidate  # noqa: E402

SEED = PKG / "seeds" / "synthetic-a.json"
CANDIDATE = FIXTURES / "WEXP-SYNTH-CANDIDATE-A"


class TestIndependenceFirewall(unittest.TestCase):
    def test_no_engine_imports_another_engine_or_a_non_shared_module(self) -> None:
        self.assertEqual(check_independence(), [])

    def test_the_two_engines_are_distinct_implementations(self) -> None:
        independent = load_engine("independent")
        reference = load_engine("reference")
        self.assertNotEqual(independent.engine_id, reference.engine_id)
        self.assertNotEqual(independent.implementation, reference.implementation)
        self.assertIsNot(type(independent).evaluate, type(reference).evaluate)

    def test_no_shared_semantic_module_exists(self) -> None:
        harness = {path.name for path in (PKG / "harness").glob("*.py")}
        self.assertEqual(
            harness,
            {"__init__.py", "canonical.py", "schema.py", "candidate.py", "engine.py",
             "environment.py", "evidence.py", "orchestrate.py"},
            msg="a new harness module must be classified before it is added",
        )


class TestCandidateLoading(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "WEXP-SYNTH-CANDIDATE-A"
        shutil.copytree(CANDIDATE, self.root)
        self.addCleanup(self._tmp.cleanup)

    def test_a_well_formed_candidate_loads(self) -> None:
        candidate = load(self.root)
        self.assertEqual(candidate.candidate_id, "WEXP-SYNTH-CANDIDATE-A")
        self.assertEqual(len(candidate.vectors), 7)

    def test_identity_includes_the_profile_digest(self) -> None:
        identity = load(self.root).identity()
        for key in ("candidate_id", "profile_sha256", "descriptor_sha256", "vector_set_sha256"):
            self.assertIn(key, identity)

    def test_a_mutated_profile_fails_closed(self) -> None:
        profile = json.loads((self.root / "profile.json").read_text())
        profile["semantics_version"] = "wexp-core-2"
        (self.root / "profile.json").write_text(json.dumps(profile))
        with self.assertRaises(CandidateError) as caught:
            load(self.root)
        self.assertIn("profile digest mismatch", str(caught.exception))

    def test_a_mutated_vector_fails_closed(self) -> None:
        target = next((self.root / "vectors").glob("*.json"))
        payload = json.loads(target.read_text())
        payload["purpose"] = "tampered"
        target.write_text(json.dumps(payload))
        with self.assertRaises(CandidateError) as caught:
            load(self.root)
        self.assertIn("SHA-256 mismatch", str(caught.exception))

    def test_a_vector_unbound_by_the_profile_fails_closed(self) -> None:
        source = next((self.root / "vectors").glob("*.json"))
        payload = json.loads(source.read_text())
        payload["vector_id"] = "WEXP-SYNTH-A-TV-9999"
        extra = self.root / "vectors" / "WEXP-SYNTH-A-TV-9999.json"
        extra.write_text(json.dumps(payload))
        with self.assertRaises(CandidateError):
            load(self.root)

    def test_directory_name_must_equal_candidate_id(self) -> None:
        renamed = self.root.parent / "WRONG-NAME"
        self.root.rename(renamed)
        with self.assertRaises(CandidateError) as caught:
            load(renamed)
        self.assertIn("must equal candidate_id", str(caught.exception))


class TestProfileTrustModel(unittest.TestCase):
    def test_unknown_schema_keyword_fails_closed(self) -> None:
        with self.assertRaises(schema_module.SchemaError):
            schema_module.validate({}, {"type": "object", "unevaluatedProperties": False})

    def test_duplicate_json_keys_are_rejected(self) -> None:
        with self.assertRaises(canonical.CanonicalError):
            canonical.loads('{"a": 1, "a": 2}')

    def test_nan_is_rejected(self) -> None:
        with self.assertRaises(canonical.CanonicalError):
            canonical.loads('{"a": NaN}')

    def test_token_roles_are_data_not_code(self) -> None:
        candidate = load(CANDIDATE)
        self.assertEqual(
            token_for(candidate.profile, "base_exceeds_boundary"), "E_BASE_EXCEEDS_BOUNDARY"
        )

    def test_a_missing_role_fails_closed(self) -> None:
        candidate = load(CANDIDATE)
        with self.assertRaises(CandidateError):
            token_for(candidate.profile, "not_a_role")


class TestQualification(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.output = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_the_synthetic_candidate_qualifies(self) -> None:
        outcome = qualify(CANDIDATE, self.output, environment_label="portable")
        self.assertEqual(outcome.status, QUALIFIED, msg=json.dumps(outcome.bundle["comparison"]["summary"]))
        self.assertEqual(outcome.bundle["comparison"]["summary"]["disagree"], 0)
        self.assertEqual(outcome.bundle["comparison"]["summary"]["expected_mismatch"], 0)

    def test_evidence_binds_the_candidate_identity_and_environment(self) -> None:
        outcome = qualify(CANDIDATE, self.output, environment_label="portable")
        identity = outcome.bundle["candidate_identity"]
        self.assertEqual(identity["candidate_id"], "WEXP-SYNTH-CANDIDATE-A")
        self.assertEqual(outcome.bundle["environment"]["label"], "portable")
        self.assertIn("not historical observations", " ".join(outcome.bundle["non_claims"]))

    def test_evidence_is_reproducible_within_an_environment(self) -> None:
        first = qualify(CANDIDATE, self.output, environment_label="portable")
        second = qualify(CANDIDATE, self.output, environment_label="portable")
        for engine in ("independent", "reference"):
            self.assertEqual(first.digests[engine], second.digests[engine])
        self.assertEqual(first.digests["comparison"], second.digests["comparison"])

    def test_engine_payload_digests_are_environment_independent(self) -> None:
        # Two environments satisfiable on any host running this suite. The
        # portable/docker/darwin triple is exercised by the matrix workflow;
        # here the point is that the payload digest does not move when the
        # environment does.
        import platform

        second_label = "darwin" if platform.system() == "Darwin" else "docker"
        first = qualify(CANDIDATE, self.output, environment_label="portable")
        second = qualify(CANDIDATE, self.output, environment_label=second_label)
        for engine in ("independent", "reference"):
            self.assertEqual(first.digests[engine], second.digests[engine])
        self.assertNotEqual(first.digests["bundle"], second.digests["bundle"])

    def test_a_single_engine_cannot_produce_a_pass(self) -> None:
        outcome = qualify(CANDIDATE, self.output, environment_label="portable", engines=("independent",))
        self.assertNotEqual(outcome.status, QUALIFIED)
        self.assertIn("at least two", outcome.bundle["comparison"]["reason"])

    def test_a_wrong_expectation_is_caught(self) -> None:
        staged = self.output / "staged" / "WEXP-SYNTH-CANDIDATE-A"
        shutil.copytree(CANDIDATE, staged)
        target = staged / "vectors" / "WEXP-SYNTH-A-TV-0001.json"
        payload = json.loads(target.read_text())
        payload["expected"]["verdict"] = "reject"
        canonical.write_canonical(target, payload)
        descriptor = json.loads((staged / "descriptor.json").read_text())
        for entry in descriptor["bound_files"]:
            if entry["path"].endswith("TV-0001.json"):
                restaged = canonical.read_artifact(target)
                entry["sha256"] = restaged.sha256
                entry["bytes"] = restaged.size
        canonical.write_canonical(staged / "descriptor.json", descriptor)
        outcome = qualify(staged, self.output, environment_label="portable")
        self.assertNotEqual(outcome.status, QUALIFIED)
        self.assertEqual(outcome.bundle["comparison"]["summary"]["expected_mismatch"], 1)


class TestEnvironmentMatrix(unittest.TestCase):
    def test_every_declared_environment_names_only_known_probes(self) -> None:
        from wexp_ref.core01.harness import environment as environment_module

        directory = PKG / "environments"
        labels = sorted(path.stem for path in directory.glob("*.json"))
        self.assertEqual(labels, ["darwin", "docker", "portable"])
        for label in labels:
            with self.subTest(environment=label):
                descriptor = environment_module.load_descriptor(label)
                self.assertEqual(descriptor["label"], label)
                self.assertTrue(set(descriptor["probes"]) <= set(environment_module.PROBES))

    def test_an_unsatisfied_requirement_fails_closed(self) -> None:
        from wexp_ref.core01.harness import environment as environment_module

        descriptor = environment_module.load_descriptor("portable")
        descriptor["require"] = {"system": "Plan9"}
        with self.assertRaises(environment_module.EnvironmentError_):
            environment_module.observe(descriptor)

    def test_an_unknown_probe_fails_closed(self) -> None:
        from wexp_ref.core01.harness import environment as environment_module

        descriptor = environment_module.load_descriptor("portable")
        descriptor["probes"] = ["not_a_probe"]
        with self.assertRaises(environment_module.EnvironmentError_):
            environment_module.observe(descriptor)

    def test_darwin_specific_observations_are_declared_as_such(self) -> None:
        from wexp_ref.core01.harness import environment as environment_module

        darwin = environment_module.load_descriptor("darwin")
        self.assertIn("filesystem_case_sensitive", darwin["environment_specific"])
        self.assertIn("temp_path_is_symlinked", darwin["environment_specific"])
        self.assertNotIn("filesystem_case_sensitive", darwin["portable_claim"])


class TestZeroEditSuccessor(unittest.TestCase):
    """Creating a successor must touch data only."""

    def test_a_successor_is_created_from_a_seed_alone(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            seed = json.loads(SEED.read_text())
            seed["candidate_id"] = "WEXP-SYNTH-CANDIDATE-B"
            # Changed token vocabulary, changed tier labels, changed ordering:
            # all data, and none of it may require a source edit.
            registry = seed["profile"]["token_registry"]
            registry["roles"]["base_exceeds_boundary"] = "E_SYNTH_CEILING_EXCEEDED"
            registry["classes"]["substantive"] = [
                "E_SYNTH_CEILING_EXCEEDED",
                "E_MISSING_REQUIRED_EVIDENCE",
                "E_COUNTER_EVIDENCE_UNRESOLVED",
            ]
            seed["profile"]["verdict_rules"]["verdicts"]["substantive"] = "downgrade"
            for entry in seed["vectors"]:
                entry["vector_id"] = entry["vector_id"].replace("SYNTH-A", "SYNTH-B")
                # Rename the token everywhere it appears in the authored
                # expectation. Order is preserved: the engines emit
                # substantive reasons in first-seen order, not sorted.
                reasons = entry["expected"].get("substantive_reasons", [])
                entry["expected"]["substantive_reasons"] = [
                    "E_SYNTH_CEILING_EXCEEDED" if token == "E_BASE_EXCEEDS_BOUNDARY" else token
                    for token in reasons
                ]
            seed_path = tmp / "seed-b.json"
            seed_path.write_text(json.dumps(seed, indent=2, sort_keys=True))

            root = new_candidate.build(seed_path, tmp)
            outcome = qualify(root, tmp / "out", environment_label="portable")
            self.assertEqual(
                outcome.status,
                QUALIFIED,
                msg=json.dumps(outcome.bundle["comparison"]["summary"]),
            )
            self.assertEqual(outcome.bundle["candidate_identity"]["candidate_id"], "WEXP-SYNTH-CANDIDATE-B")


if __name__ == "__main__":
    unittest.main()


class TestSchedulingPolicy(unittest.TestCase):
    """The cost-aware policy must reduce execution frequency, never the gate."""

    def setUp(self) -> None:
        from wexp_ref.core01.tools import matrix_policy

        self.policy = matrix_policy

    def test_push_schedules_the_portable_leg_only(self) -> None:
        plan = self.policy.plan("push")
        self.assertEqual(plan["environments"], ["portable"])
        self.assertFalse(plan["full_matrix"])
        self.assertFalse(plan["run_portability_comparison"])

    def test_pull_request_schedules_the_full_matrix(self) -> None:
        plan = self.policy.plan("pull_request")
        self.assertEqual(plan["environments"], ["portable", "docker", "darwin"])
        self.assertTrue(plan["full_matrix"])
        self.assertTrue(plan["run_portability_comparison"])

    def test_workflow_dispatch_schedules_the_full_matrix(self) -> None:
        plan = self.policy.plan("workflow_dispatch")
        self.assertEqual(plan["environments"], ["portable", "docker", "darwin"])
        self.assertTrue(plan["full_matrix"])

    def test_a_push_only_result_cannot_claim_qualification_readiness(self) -> None:
        push = self.policy.plan("push")
        self.assertFalse(push["sufficient_for_qualification_readiness"])
        self.assertEqual(push["observation_scope"], self.policy.SCOPE_DEVELOPER_FEEDBACK)
        self.assertIn("does not satisfy", push["note"])

    def test_an_unrecognised_event_errs_toward_more_observation(self) -> None:
        # Erring toward the full matrix is safe; erring toward less would
        # silently weaken the gate.
        plan = self.policy.plan("schedule")
        self.assertTrue(plan["full_matrix"])

    def test_the_workflow_uses_the_policy_rather_than_a_static_matrix(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "core01-qualification.yml").read_text(encoding="utf-8")
        self.assertIn("src/wexp_ref/core01/tools/matrix_policy.py", workflow)
        self.assertIn("fromJSON(needs.plan.outputs.include)", workflow)
        self.assertIn("needs.plan.outputs.full_matrix == 'true'", workflow)
        self.assertIn("--require-full-matrix", workflow)

    def test_the_workflow_contains_no_candidate_specific_logic(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "core01-qualification.yml").read_text(encoding="utf-8")
        candidates = sorted(
            path.name for path in (FIXTURES).iterdir() if path.is_dir()
        )
        # The default input names one candidate; nothing else may branch on a
        # candidate identity.
        for name in candidates:
            self.assertLessEqual(
                workflow.count(name), 1, msg=f"{name} appears more than once in the workflow"
            )
        self.assertNotIn("if: ${{ env.CANDIDATE ==", workflow)


class TestFullMatrixGate(unittest.TestCase):
    """A partial comparison is supporting evidence, never the formal gate."""

    def setUp(self) -> None:
        from wexp_ref.core01.tools import compare_environments

        self.tool = compare_environments
        self._tmp = tempfile.TemporaryDirectory()
        self.output = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.bundles = {
            label: qualify(CANDIDATE, self.output / label, environment_label="portable").bundle
            for label in ("portable", "docker", "darwin")
        }

    def test_all_three_environments_make_a_full_matrix_observation(self) -> None:
        report = self.tool.compare(self.bundles)
        self.assertTrue(report["full_matrix_observation"])
        self.assertEqual(report["missing_required_environments"], [])
        self.assertTrue(report["sufficient_for_qualification_readiness"])

    def test_a_missing_environment_cannot_claim_the_full_matrix(self) -> None:
        partial = {k: v for k, v in self.bundles.items() if k != "darwin"}
        report = self.tool.compare(partial)
        self.assertFalse(report["full_matrix_observation"])
        self.assertEqual(report["missing_required_environments"], ["darwin"])
        self.assertFalse(report["sufficient_for_qualification_readiness"])
        self.assertIn("supporting evidence only", " ".join(report["non_claims"]))

    def test_the_required_environment_set_is_the_full_matrix(self) -> None:
        from wexp_ref.core01.tools import matrix_policy

        self.assertEqual(
            self.tool.REQUIRED_FULL_MATRIX,
            {entry["environment"] for entry in matrix_policy.FULL_MATRIX},
        )


class TestInfrastructureAvailability(unittest.TestCase):
    """Execution availability is not a qualification result."""

    def test_infrastructure_unavailability_has_its_own_vocabulary(self) -> None:
        from wexp_ref.core01.harness.orchestrate import NOT_QUALIFIED
        from wexp_ref.core01.tools import compare_environments, matrix_policy

        self.assertNotEqual(matrix_policy.INFRASTRUCTURE_UNAVAILABLE, NOT_QUALIFIED)
        self.assertNotEqual(matrix_policy.INFRASTRUCTURE_UNAVAILABLE, compare_environments.NOT_PORTABLE)
        self.assertNotIn("FAIL", matrix_policy.INFRASTRUCTURE_UNAVAILABLE)

    def test_an_absent_environment_is_reported_as_incomplete_not_as_failure(self) -> None:
        from wexp_ref.core01.tools import compare_environments

        self.assertNotEqual(compare_environments.INCOMPLETE, compare_environments.NOT_PORTABLE)
        self.assertIn("INCOMPLETE", compare_environments.INCOMPLETE)


class TestClaimAlgebraDifferential(unittest.TestCase):
    """The two independent claim algebras must agree across the whole powerset.

    The independent evaluator compares qualifier sets; the reference
    implementation does mask arithmetic over rank-encoded claims. They are
    written differently on purpose, so agreement is evidence rather than a
    tautology.
    """

    def setUp(self) -> None:
        import itertools

        from wexp_ref.core01.engines.independent import claims
        from wexp_ref.core01.engines.reference import algebra

        self.independent = claims
        self.reference = algebra
        self.profile = {
            "orderings": {
                "base": ["observation", "intent", "invocation", "execution"],
                "qualifier": ["PROV", "IV"],
            },
            "qualifier_admissibility": {"PROV": ["execution"]},
            "semantics_version": "wexp-core-1",
            "verdict_rules": {
                "verdicts": {"fatal": "reject", "substantive": "downgrade", "default": "accept"}
            },
        }
        bases = self.profile["orderings"]["base"]
        qualifiers = self.profile["orderings"]["qualifier"]
        self.universe = []
        for base in bases:
            for size in range(len(qualifiers) + 1):
                for combination in itertools.combinations(qualifiers, size):
                    claim = {"base": base, "qualifiers": list(combination)}
                    try:
                        self.independent.normalise(self.profile, claim)
                    except self.independent.ClaimError:
                        continue
                    self.universe.append(claim)

    def test_the_admissible_powerset_is_not_trivially_small(self) -> None:
        self.assertEqual(len(self.universe), 10)

    def test_domination_agrees_over_every_ordered_pair(self) -> None:
        for left in self.universe:
            for right in self.universe:
                with self.subTest(left=left, right=right):
                    self.assertEqual(
                        self.independent.dominates(self.profile, left, right),
                        self.reference.dominates(self.profile, left, right),
                    )

    def test_the_support_relation_agrees_over_every_ordered_pair(self) -> None:
        for left in self.universe:
            for right in self.universe:
                with self.subTest(left=left, right=right):
                    self.assertEqual(
                        self.independent.relation(self.profile, left, right),
                        self.reference.relation(self.profile, left, right),
                    )

    def test_maximal_claims_agree(self) -> None:
        self.assertEqual(
            self.independent.maximal(self.profile, self.universe),
            self.reference.maximal(self.profile, self.universe),
        )

    def test_both_reject_the_same_inadmissible_claims(self) -> None:
        inadmissible = [
            {"base": "observation", "qualifiers": ["PROV"]},
            {"base": "execution", "qualifiers": ["IV", "IV"]},
            {"base": "not-a-base", "qualifiers": []},
            {"base": "execution", "qualifiers": ["NOPE"]},
            {"base": "execution", "qualifiers": "IV"},
        ]
        for claim in inadmissible:
            with self.subTest(claim=claim):
                with self.assertRaises(self.independent.ClaimError):
                    self.independent.normalise(self.profile, claim)
                with self.assertRaises(self.reference.ClaimRejected):
                    self.reference.normalise(self.profile, claim)

    def test_qualifier_admissibility_is_data_not_code(self) -> None:
        # Removing the restriction from the profile admits the claim in both
        # engines, with no source change.
        permissive = dict(self.profile)
        permissive["qualifier_admissibility"] = {}
        claim = {"base": "observation", "qualifiers": ["PROV"]}
        self.assertEqual(
            self.independent.normalise(permissive, claim),
            self.reference.normalise(permissive, claim),
        )

    def test_fixed_rejection_projections_are_identical(self) -> None:
        self.assertEqual(
            self.independent.fixed_rejection(self.profile, ["E_X"]),
            self.reference.fixed_rejection(self.profile, ["E_X"]),
        )

    def test_limitation_union_preserves_first_seen_order_in_both(self) -> None:
        values = ["b", "a", "b", "c", "a"]
        self.assertEqual(
            self.independent.stable_unique(values),
            self.reference.union_in_order(values),
        )
        self.assertEqual(self.independent.stable_unique(values), ["b", "a", "c"])

    def test_neither_algebra_can_see_an_expectation(self) -> None:
        import inspect

        for module in (self.independent, self.reference):
            with self.subTest(module=module.__name__):
                source = inspect.getsource(module)
                self.assertNotIn("expected", source)


class TestCoreIngressDifferential(unittest.TestCase):
    """Ordered Core ingress, implemented independently in both engines.

    The independent evaluator runs a list of guard callables; the reference
    implementation walks a numbered position table. They must agree on which
    position wins and on the token emitted there.
    """

    def setUp(self) -> None:
        from wexp_ref.core01.engines.independent import ingress
        from wexp_ref.core01.engines.reference import gate

        self.ingress = ingress
        self.gate = gate
        self.profile = {
            "semantics_version": "wexp-core-1",
            "orderings": {"base": ["observation", "execution"], "qualifier": ["IV"]},
            "recorder_relation_components": [
                "profile_identifier", "relation_token", "subject_ref",
                "object_ref", "basis_refs", "limitations",
            ],
            "token_registry": {
                "roles": {
                    "unknown_critical": "E_UNKNOWN_CRITICAL_SEMANTIC",
                    "base_exceeds_boundary": "E_BASE_EXCEEDS_BOUNDARY",
                    "missing_required_evidence": "E_MISSING_REQUIRED_EVIDENCE",
                    "counter_evidence_unresolved": "E_COUNTER_EVIDENCE_UNRESOLVED",
                    "qualifier_not_evaluated": "E_IV_NOT_EVALUATED",
                    "malformed_normalized_input": "E_MALFORMED_NORMALIZED_INPUT",
                    "unsupported_semantics_version": "E_UNSUPPORTED_SEMANTICS_VERSION",
                    "profile_mapping_invalid": "E_PROFILE_MAPPING_INVALID",
                    "claim_out_of_domain": "E_CLAIM_OUT_OF_DOMAIN",
                },
                "classes": {"fatal": [], "substantive": [], "gap": []},
                "foreign_rejected": [],
                "derived_only": [
                    "E_MALFORMED_NORMALIZED_INPUT", "E_UNSUPPORTED_SEMANTICS_VERSION",
                    "E_PROFILE_MAPPING_INVALID", "E_CLAIM_OUT_OF_DOMAIN",
                ],
                "supplied_fatal": ["E_UNKNOWN_CRITICAL_SEMANTIC", "E_INTEGRITY_INVALID"],
            },
            "verdict_rules": {"verdicts": {"fatal": "reject", "substantive": "downgrade", "default": "accept"}},
        }

    def both(self, value):
        a = self.ingress.evaluate_order(self.profile, value)
        b = self.gate.screen(self.profile, value)
        return a, b

    def test_a_well_formed_input_passes_both(self) -> None:
        a, b = self.both({"semantics_version": "wexp-core-1", "fatal_conditions": []})
        self.assertIsNone(a)
        self.assertIsNone(b)

    def test_position_1_non_record_and_missing_version(self) -> None:
        for value in ([], {"fatal_conditions": []}, {"semantics_version": 7}):
            with self.subTest(value=value):
                a, b = self.both(value)
                self.assertEqual(a[0], "E_MALFORMED_NORMALIZED_INPUT")
                self.assertEqual(a[0], b[0])

    def test_position_2_unsupported_version(self) -> None:
        a, b = self.both({"semantics_version": "wexp-core-2"})
        self.assertEqual(a[0], "E_UNSUPPORTED_SEMANTICS_VERSION")
        self.assertEqual(a[0], b[0])

    def test_position_3_member_typing(self) -> None:
        a, b = self.both({"semantics_version": "wexp-core-1", "base_findings": {}})
        self.assertEqual(a[0], "E_MALFORMED_NORMALIZED_INPUT")
        self.assertEqual(a[0], b[0])

    def test_position_4_derived_token_may_not_be_supplied(self) -> None:
        value = {"semantics_version": "wexp-core-1", "fatal_conditions": ["E_PROFILE_MAPPING_INVALID"]}
        a, b = self.both(value)
        self.assertEqual(a[0], "E_PROFILE_MAPPING_INVALID")
        self.assertEqual(a[0], b[0])

    def test_position_4_token_outside_the_supplied_category(self) -> None:
        value = {"semantics_version": "wexp-core-1", "fatal_conditions": ["E_SOMETHING_ELSE"]}
        a, b = self.both(value)
        self.assertEqual(a[0], "E_PROFILE_MAPPING_INVALID")
        self.assertEqual(a[0], b[0])

    def test_a_permitted_supplied_fatal_passes_ingress(self) -> None:
        # Position 5 belongs to the appraisal, not to ingress.
        value = {"semantics_version": "wexp-core-1", "fatal_conditions": ["E_UNKNOWN_CRITICAL_SEMANTIC"]}
        a, b = self.both(value)
        self.assertIsNone(a)
        self.assertIsNone(b)

    def test_an_earlier_position_wins_over_a_later_one(self) -> None:
        # Both a bad version and a bad supplied token: position 2 must win.
        value = {"semantics_version": "nope", "fatal_conditions": ["E_PROFILE_MAPPING_INVALID"]}
        a, b = self.both(value)
        self.assertEqual(a[0], "E_UNSUPPORTED_SEMANTICS_VERSION")
        self.assertEqual(a[0], b[0])

    def test_an_undeclared_position_fails_closed_in_both(self) -> None:
        profile = json.loads(json.dumps(self.profile))
        del profile["token_registry"]["roles"]["unsupported_semantics_version"]
        value = {"semantics_version": "wexp-core-2"}
        with self.assertRaises(self.ingress.IngressRejection):
            self.ingress.evaluate_order(profile, value)
        with self.assertRaises(self.gate.GateRefusal):
            self.gate.screen(profile, value)


class TestRecorderRelationEqualityDifferential(unittest.TestCase):
    """Six-component equality, tuple keys versus canonical strings."""

    def setUp(self) -> None:
        from wexp_ref.core01.engines.independent import claims
        from wexp_ref.core01.engines.reference import algebra

        self.independent = claims
        self.reference = algebra
        self.profile = {
            "recorder_relation_components": [
                "profile_identifier", "relation_token", "subject_ref",
                "object_ref", "basis_refs", "limitations",
            ]
        }

    def relation(self, **overrides):
        base = {
            "profile_identifier": "p:1", "relation_token": "recorded-by",
            "subject_ref": "s", "object_ref": "o",
            "basis_refs": ["b1"], "limitations": [],
        }
        base.update(overrides)
        return base

    def test_identical_relations_deduplicate_in_both(self) -> None:
        rels = [self.relation(), self.relation()]
        self.assertEqual(len(self.independent.unique_relations(self.profile, rels)), 1)
        self.assertEqual(len(self.reference.distinct_relations(self.profile, rels)), 1)

    def test_a_difference_in_any_component_keeps_both(self) -> None:
        for field, value in (
            ("profile_identifier", "p:2"), ("relation_token", "other"),
            ("subject_ref", "s2"), ("object_ref", "o2"),
            ("basis_refs", ["b2"]), ("limitations", ["l"]),
        ):
            with self.subTest(component=field):
                rels = [self.relation(), self.relation(**{field: value})]
                self.assertEqual(len(self.independent.unique_relations(self.profile, rels)), 2)
                self.assertEqual(len(self.reference.distinct_relations(self.profile, rels)), 2)

    def test_first_seen_order_is_preserved_identically(self) -> None:
        rels = [self.relation(subject_ref="b"), self.relation(subject_ref="a"), self.relation(subject_ref="b")]
        a = [r["subject_ref"] for r in self.independent.unique_relations(self.profile, rels)]
        b = [r["subject_ref"] for r in self.reference.distinct_relations(self.profile, rels)]
        self.assertEqual(a, ["b", "a"])
        self.assertEqual(a, b)

    def test_a_missing_component_fails_closed_in_both(self) -> None:
        broken = self.relation()
        del broken["object_ref"]
        with self.assertRaises(self.independent.ClaimError):
            self.independent.unique_relations(self.profile, [broken])
        with self.assertRaises(self.reference.ClaimRejected):
            self.reference.distinct_relations(self.profile, [broken])

    def test_an_undeclared_component_set_fails_closed_in_both(self) -> None:
        with self.assertRaises(self.independent.ClaimError):
            self.independent.unique_relations({}, [self.relation()])
        with self.assertRaises(self.reference.ClaimRejected):
            self.reference.distinct_relations({}, [self.relation()])


class TestStructuralOrderProductRule(unittest.TestCase):
    """Section 4.5: (b1,A1) <= (b2,A2) iff b1 <= b2 and A1 is a subset of A2.

    Both conjuncts are required. The frozen text names two incomparable
    examples explicitly, and both are asserted here so a future change that
    over-orders claims fails loudly.
    """

    def setUp(self) -> None:
        from wexp_ref.core01.engines.independent import claims
        from wexp_ref.core01.engines.reference import algebra

        self.independent = claims
        self.reference = algebra
        self.profile = {
            "orderings": {
                "base": ["observation", "intent", "invocation", "execution"],
                "qualifier": ["PROV", "IV"],
            },
            "qualifier_admissibility": {"PROV": ["execution"]},
        }

    def claim(self, base, qualifiers=()):
        return {"base": base, "qualifiers": list(qualifiers)}

    def both(self, supported, asserted):
        return (
            self.independent.relation(self.profile, supported, asserted),
            self.reference.relation(self.profile, supported, asserted),
        )

    def test_the_two_incomparable_examples_from_the_specification(self) -> None:
        # "(execution, {PROV}) and (execution, {IV}) are incomparable, as are
        #  (invocation, {IV}) and (execution, {})."
        for left, right in (
            (self.claim("execution", ["PROV"]), self.claim("execution", ["IV"])),
            (self.claim("invocation", ["IV"]), self.claim("execution")),
        ):
            with self.subTest(left=left, right=right):
                a, b = self.both(left, right)
                self.assertEqual(a, "incomparable")
                self.assertEqual(a, b)
                self.assertFalse(self.independent.dominates(self.profile, left, right))
                self.assertFalse(self.reference.dominates(self.profile, left, right))

    def test_a_lower_base_with_an_equal_qualifier_set_is_below(self) -> None:
        # The C06 defect: this was wrongly reported incomparable.
        a, b = self.both(self.claim("invocation", ["IV"]), self.claim("execution", ["IV"]))
        self.assertEqual(a, "support-below-claim")
        self.assertEqual(a, b)

    def test_a_lower_base_with_a_subset_qualifier_set_is_below(self) -> None:
        a, b = self.both(self.claim("intent"), self.claim("execution", ["IV"]))
        self.assertEqual(a, "support-below-claim")
        self.assertEqual(a, b)

    def test_a_superset_qualifier_set_at_a_higher_base_is_above(self) -> None:
        a, b = self.both(self.claim("execution", ["IV"]), self.claim("invocation", ["IV"]))
        self.assertEqual(a, "support-above-claim")
        self.assertEqual(a, b)

    def test_equality_is_reported_as_equal(self) -> None:
        a, b = self.both(self.claim("execution"), self.claim("execution"))
        self.assertEqual(a, "equal")
        self.assertEqual(a, b)

    def test_domination_is_strict_and_never_reflexive(self) -> None:
        claim = self.claim("execution", ["IV"])
        self.assertFalse(self.independent.dominates(self.profile, claim, claim))
        self.assertFalse(self.reference.dominates(self.profile, claim, claim))

    def test_the_order_is_antisymmetric_across_the_admissible_set(self) -> None:
        import itertools

        universe = []
        for base in self.profile["orderings"]["base"]:
            for size in range(3):
                for combo in itertools.combinations(self.profile["orderings"]["qualifier"], size):
                    claim = self.claim(base, combo)
                    try:
                        self.independent.normalise(self.profile, claim)
                    except self.independent.ClaimError:
                        continue
                    universe.append(claim)
        for left in universe:
            for right in universe:
                with self.subTest(left=left, right=right):
                    a = self.independent.dominates(self.profile, left, right)
                    b = self.reference.dominates(self.profile, left, right)
                    self.assertEqual(a, b)
                    if a:
                        # strict order: never both directions
                        self.assertFalse(self.independent.dominates(self.profile, right, left))


class TestFrozenCoreQualificationFixes(unittest.TestCase):
    """C09, C12 and C14 against the frozen Core-01 candidate."""

    # The Core-01 set lives in wexp-vectors, not here. CI checks out the pinned
    # corpus and points this at it; without it there is nothing to assert against,
    # so the class skips rather than silently testing nothing.
    CANDIDATE = Path(os.environ.get("WEXP_CORE01_CORPUS", "")) if os.environ.get("WEXP_CORE01_CORPUS") else None

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        if cls.CANDIDATE is None or not cls.CANDIDATE.is_dir():
            raise unittest.SkipTest(
                "set WEXP_CORE01_CORPUS to the pinned wexp-vectors Core-01 set"
            )
        cls.outcome = qualify(cls.CANDIDATE, Path(cls._tmp.name), environment_label="portable")
        cls.by_engine = {
            e["engine_id"]: {r["vector_id"]: r["actual"] for r in e["results"]}
            for e in cls.outcome.bundle["engines"]
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def vector(self, fixture):
        for path in sorted((self.CANDIDATE / "vectors").glob("*.json")):
            payload = json.loads(path.read_text())
            if payload["source_fixture"] == fixture:
                return payload
        raise AssertionError(f"no vector for fixture {fixture}")

    def actual(self, fixture, engine="independent"):
        return self.by_engine[engine][self.vector(fixture)["vector_id"]]

    def test_the_whole_candidate_qualifies(self) -> None:
        summary = self.outcome.bundle["comparison"]["summary"]
        self.assertEqual(summary["vectors"], 16)
        self.assertEqual(summary["agree"], 16)
        self.assertEqual(summary["disagree"], 0)
        self.assertEqual(summary["expected_mismatch"], 0)
        self.assertEqual(summary["uncovered_requirements"], 0)

    def test_c06_reports_a_structurally_lower_alternative_as_below(self) -> None:
        actual = self.actual("C06")
        relations = {
            (r["supported_claim"]["base"], tuple(r["supported_claim"]["qualifiers"])): r["relation"]
            for r in actual["support_relations"]
        }
        self.assertEqual(relations[("invocation", ("IV",))], "support-below-claim")

    def test_c09_returns_the_fixed_rejection_projection(self) -> None:
        for engine in ("independent", "reference"):
            with self.subTest(engine=engine):
                actual = self.actual("C09", engine)
                self.assertEqual(actual["verdict"], "reject")
                self.assertEqual(actual["fatal_reasons"], ["E_CLAIM_OUT_OF_DOMAIN"])
                self.assertIsNone(actual["asserted_claim"])
                self.assertIsNone(actual["target"])
                self.assertFalse(actual["asserted_claim_supported"])

    def test_c09_leaks_no_implementation_exception(self) -> None:
        for engine in ("independent", "reference"):
            with self.subTest(engine=engine):
                actual = self.actual("C09", engine)
                self.assertNotIn("engine_rejected", actual)
                self.assertNotIn("engine_error", actual)

    def test_c09_both_engines_return_the_identical_result(self) -> None:
        self.assertEqual(self.actual("C09", "independent"), self.actual("C09", "reference"))

    def test_c12_carries_the_boundary_limitation_through(self) -> None:
        for engine in ("independent", "reference"):
            with self.subTest(engine=engine):
                self.assertIn("L-boundary", self.actual("C12", engine)["inherited_limitations"])

    def test_c14_derives_the_gap_and_downgrades(self) -> None:
        for engine in ("independent", "reference"):
            with self.subTest(engine=engine):
                actual = self.actual("C14", engine)
                self.assertIn("E_COUNTER_EVIDENCE_NOT_EVALUATED", actual["evaluation_gaps"])
                self.assertEqual(actual["verdict"], "downgrade")

    def test_c14_a_defeating_entry_for_another_claim_does_not_bleed_across(self) -> None:
        # Section 8.2: "a defeating entry for one claim never changes the status
        # of a separate not-evaluated entry for another claim."
        actual = self.actual("C14")
        self.assertNotIn("E_COUNTER_EVIDENCE_DEFEATING", actual["substantive_reasons"])


class TestSingleReadInvariant(unittest.TestCase):
    """GAP-0014: an artifact that contributes to an evidence identity is read once.

    Hashing one read and parsing a second cannot be proven to describe the same
    bytes. These tests assert the property structurally — that there is no second
    read — rather than asserting that two reads happened to agree.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_the_digest_is_over_the_buffer_that_gets_parsed(self) -> None:
        target = self.dir / "a.json"
        raw = b'{\n  "b": 2,\n  "a": 1\n}\n'
        target.write_bytes(raw)
        artifact = canonical.read_artifact(target)
        self.assertEqual(artifact.raw, raw)
        self.assertEqual(artifact.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(artifact.size, len(raw))
        self.assertEqual(artifact.json(), json.loads(raw))

    def test_the_digest_is_over_original_bytes_not_a_re_serialisation(self) -> None:
        target = self.dir / "spaced.json"
        raw = b'{"a":   1}'
        target.write_bytes(raw)
        artifact = canonical.read_artifact(target)
        self.assertEqual(artifact.sha256, hashlib.sha256(raw).hexdigest())
        self.assertNotEqual(artifact.sha256, canonical.canonical_sha256({"a": 1}))

    def test_loading_a_candidate_reads_every_artifact_exactly_once(self) -> None:
        staged = self.dir / "WEXP-SYNTH-CANDIDATE-A"
        shutil.copytree(CANDIDATE, staged)
        counts: dict[str, int] = {}
        original = Path.read_bytes

        def counting(self_path: Path) -> bytes:
            counts[str(self_path)] = counts.get(str(self_path), 0) + 1
            return original(self_path)

        Path.read_bytes = counting  # type: ignore[method-assign]
        try:
            load(staged)
        finally:
            Path.read_bytes = original  # type: ignore[method-assign]

        repeated = {path: n for path, n in counts.items() if n > 1 and str(staged) in path}
        self.assertEqual(repeated, {}, msg=f"artifact read more than once: {repeated}")
        self.assertTrue(counts, msg="the counter observed no reads at all")

    def test_a_mutation_after_the_read_cannot_desynchronise_digest_and_content(self) -> None:
        """If a second read existed, this fixture would expose it: every read after
        the first returns different bytes. A consistent result proves there is
        exactly one read backing both the digest and the payload."""
        staged = self.dir / "WEXP-SYNTH-CANDIDATE-A"
        shutil.copytree(CANDIDATE, staged)
        victim = sorted((staged / "vectors").glob("*.json"))[0]
        original = Path.read_bytes
        served: dict[str, bytes] = {}

        def mutating(self_path: Path) -> bytes:
            raw = original(self_path)
            if self_path.name == victim.name and "vectors" in self_path.parts:
                if self_path.name in served:
                    return b'{"tampered": true}'
                served[self_path.name] = raw
            return raw

        Path.read_bytes = mutating  # type: ignore[method-assign]
        try:
            candidate = load(staged)
        finally:
            Path.read_bytes = original  # type: ignore[method-assign]

        vector = next(v for v in candidate.vectors if v.path.name == victim.name)
        first_read = served[victim.name]
        self.assertEqual(vector.sha256, hashlib.sha256(first_read).hexdigest())
        self.assertEqual(vector.payload, json.loads(first_read))

    def test_malformed_bytes_still_fail(self) -> None:
        for name, raw in (
            ("truncated.json", b'{"a": '),
            ("duplicate.json", b'{"a": 1, "a": 2}'),
            ("constant.json", b'{"a": NaN}'),
            ("latin1.json", '{"a": "é"}'.encode("latin-1")),
        ):
            target = self.dir / name
            target.write_bytes(raw)
            with self.subTest(name=name):
                with self.assertRaises(canonical.CanonicalError):
                    canonical.read_artifact(target).json()

    def test_symlinked_artifacts_are_still_refused(self) -> None:
        real = self.dir / "real.json"
        real.write_bytes(b"{}")
        link = self.dir / "link.json"
        link.symlink_to(real)
        with self.assertRaises(canonical.CanonicalError):
            canonical.read_artifact(link)

    def test_the_independent_read_helpers_are_gone(self) -> None:
        """Keeping them would let a future caller pair one with a load and
        reintroduce exactly the defect this change removes."""
        self.assertFalse(hasattr(canonical, "file_sha256"))
        self.assertFalse(hasattr(canonical, "file_bytes"))
