"""Independent evaluator — profile-driven path.

Classification: **ASSURANCE-CRITICAL — MUST REMAIN INDEPENDENT**

One of two independent implementations. This one derives the appraisal by
building dictionaries of support entries keyed by normalised claim, then
filtering. The reference implementation walks an ordered rule pass over a
mutable record. Only the specification is shared; no semantic code is.

Fidelity rule for this path: it reproduces the frozen Candidate-001 behaviour,
including its deliberate absences. It does not compute recorder relations, does
not appraise composition, does not branch on evaluation scope, and does not
derive fatal conditions — because the frozen slice does none of those. Those
are recorded in the successor-capability register, not implemented here.

Candidate-variable vocabulary comes from the profile: orderings, qualifier
admissibility, qualifier independence requirements, status domains, token roles
and classes, and verdict labels. This module never names a candidate, a token
string, or a tier.

It imports only SHARED-INFRASTRUCTURE-SAFE helpers and its own claim algebra,
and never the reference implementation. It never reads a vector's expectation.
"""

from __future__ import annotations

import copy
from typing import Any

from wexp_ref.core01.harness.candidate import Candidate, Vector, known_tokens, token_for

from . import claims as claim_algebra, ingress

ENGINE_ID = "independent"
IMPLEMENTATION = "independent evaluator, keyed support-entry derivation, profile-driven"


class _Reject(Exception):
    """Raised when the input is outside this candidate's admissible slice."""


def _domain(profile: dict[str, Any], name: str) -> frozenset[str]:
    return frozenset(profile["status_domains"].get(name) or ())


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise _Reject(detail)


def _passes(profile: dict[str, Any], finding: dict[str, Any]) -> bool:
    assessment = _domain(profile, "assessment")
    binding = finding.get("target_binding")
    validation = finding.get("semantic_validation")
    _require(binding in assessment, f"target_binding outside domain: {binding!r}")
    _require(validation in assessment, f"semantic_validation outside domain: {validation!r}")
    return binding == "supported" and validation == "supported"


def _qualifier_independence_ok(profile: dict[str, Any], qualifier: str, observed: Any) -> bool:
    """Which independence value a qualifier requires is candidate data."""

    required = (profile.get("qualifier_independence") or {}).get(qualifier)
    if required is None:
        return True
    _require(observed in _domain(profile, "independence"), f"independence outside domain: {observed!r}")
    return observed == required


def _affects(profile: dict[str, Any], affected: Any, claim_list: list[dict[str, Any]]) -> bool:
    if affected == "all-admissible-claims":
        return True
    _require(isinstance(affected, list), "affected_claims must be an array or all-admissible-claims")
    affected_keys = {claim_algebra.key(profile, item) for item in affected}
    return any(claim_algebra.key(profile, claim) in affected_keys for claim in claim_list)


def evaluate(vector: Vector, candidate: Candidate) -> dict[str, Any]:
    profile = candidate.profile
    value = vector.input
    try:
        # Ordered Core ingress precedes appraisal. Positions 1-4 are decided
        # here; a win at any of them is the only Core result for that input.
        derived = ingress.evaluate_order(profile, value)
        if derived is not None:
            token, _detail = derived
            return claim_algebra.fixed_rejection(profile, [token])

        # Position 5: a valid supplied fatal set. Supplied, never derived.
        fatal = list(value.get("fatal_conditions") or [])
        if fatal:
            return claim_algebra.fixed_rejection(profile, fatal)

        boundary = value.get("boundary_finding") or {}
        _require(
            boundary.get("status") == "supported" and boundary.get("target_binding") == "supported",
            "this candidate requires an accepted, target-bound Boundary Ceiling",
        )
        ceiling = boundary.get("ceiling_base")
        bases = profile["orderings"]["base"]
        _require(ceiling in bases, "accepted boundary lacks a valid ceiling")
        ceiling_rank = bases.index(ceiling)

        support: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
        substantive: list[str] = []

        for finding in value.get("base_findings") or []:
            base = finding.get("base")
            _require(base in bases, "base finding uses an unknown base")
            if not _passes(profile, finding):
                continue
            if bases.index(base) > ceiling_rank:
                substantive.append(token_for(profile, "base_exceeds_boundary"))
                continue
            claim = {"base": base, "qualifiers": []}
            key = claim_algebra.key(profile, claim)
            _require(key not in support, "duplicate semantic base finding")
            support[key] = {
                "claim": claim,
                "basis_refs": claim_algebra.stable_unique(
                    [*boundary.get("basis_refs", []), *finding.get("basis_refs", [])]
                ),
                "limitations": claim_algebra.stable_unique(
                    [*boundary.get("limitations", []), *finding.get("limitations", [])]
                ),
            }

        for finding in value.get("qualifier_findings") or []:
            base = finding.get("qualified_base")
            qualifier = finding.get("qualifier")
            _require(
                base in bases and qualifier in profile["orderings"]["qualifier"],
                "qualifier finding is outside this candidate",
            )
            base_key = (base, ())
            admitted = (
                _passes(profile, finding)
                and _qualifier_independence_ok(profile, qualifier, finding.get("independence_validation"))
            )
            # A qualified claim is lifted only from an already-supported base.
            if not admitted or base_key not in support:
                continue
            claim = claim_algebra.normalise(profile, {"base": base, "qualifiers": [qualifier]})
            key = claim_algebra.key(profile, claim)
            _require(key not in support, "duplicate semantic qualifier finding")
            parent = support[base_key]
            support[key] = {
                "claim": claim,
                "basis_refs": claim_algebra.stable_unique(
                    [*parent["basis_refs"], *finding.get("basis_refs", [])]
                ),
                "limitations": claim_algebra.stable_unique(
                    [*parent["limitations"], *finding.get("limitations", [])]
                ),
            }

        entries = sorted(
            support.values(), key=lambda entry: claim_algebra.sort_key(profile, entry["claim"])
        )
        supported_claims = [entry["claim"] for entry in entries]
        maximal = claim_algebra.maximal(profile, supported_claims)

        # Position 6 of the ordered algorithm: an asserted claim outside the
        # admissible domain is a fixed rejection, not an implementation error.
        try:
            asserted = claim_algebra.normalise(profile, value["asserted_claim"])
        except claim_algebra.ClaimError:
            return claim_algebra.fixed_rejection(
                profile, [token_for(profile, "claim_out_of_domain")]
            )
        asserted_supported = claim_algebra.key(profile, asserted) in support
        exceeds = token_for(profile, "base_exceeds_boundary")
        if not asserted_supported and exceeds not in substantive:
            substantive.append(token_for(profile, "missing_required_evidence"))

        relevant = [asserted, *supported_claims]
        counter_domain = _domain(profile, "counter-evidence")

        gap_tokens: list[str] = []
        gap_entries: list[dict[str, Any]] = []
        inherited = list(value.get("inherited_limitations") or [])

        # Section 8.2: only not-evaluated, unresolved-material and defeating
        # block, and only for entries whose affected claims include the
        # asserted claim or all-admissible-claims.
        blocking = ("not-evaluated", "unresolved-material", "defeating")
        counter_blocks = False
        for counter in value.get("counter_evidence") or []:
            status = counter.get("status")
            _require(status in counter_domain, f"counter status outside this candidate: {status!r}")
            if status not in blocking:
                continue
            if not _affects(profile, counter.get("affected_claims"), [asserted]):
                continue
            counter_blocks = True
            inherited.extend(counter.get("limitations", []))
            # The Core status token precedes the entry's registered reasons,
            # matching how the normative vector table renders the set.
            if status == "unresolved-material":
                substantive.append(token_for(profile, "counter_evidence_unresolved"))
            elif status == "defeating":
                substantive.append(token_for(profile, "counter_evidence_defeating"))
            substantive.extend(counter.get("reasons", []))
            if status == "not-evaluated":
                token = token_for(profile, "counter_evidence_not_evaluated")
                gap_tokens.append(token)
                gap_entries.append(
                    {
                        "token": token,
                        "target": value.get("target"),
                        "evaluation_context_ref": (value.get("evaluation_context") or {}).get("id"),
                        "affected_claims": copy.deepcopy(counter.get("affected_claims")),
                        "basis_refs": list(counter.get("basis_refs", [])),
                        "limitations": list(counter.get("limitations", [])),
                    }
                )

        registered_gaps = frozenset(profile["token_registry"]["classes"]["gap"])
        for gap in value.get("profile_evaluation_gaps") or []:
            _require(gap.get("token") in registered_gaps, "unregistered profile gap token")
            if not _affects(profile, gap.get("affected_claims"), relevant):
                continue
            gap_tokens.append(gap["token"])
            gap_entries.append(
                {
                    "token": gap["token"],
                    "target": gap["target"],
                    "evaluation_context_ref": gap["evaluation_context_ref"],
                    "affected_claims": copy.deepcopy(gap["affected_claims"]),
                    "basis_refs": list(gap["basis_refs"]),
                    "limitations": list(gap["limitations"]),
                }
            )
            inherited.extend(gap["limitations"])

        # Section 8.1: the union is boundary limitations, every support-entry
        # limitation, the input's inherited limitations, and the limitations of
        # each applicable counter or profile-gap entry.
        inherited.extend(boundary.get("limitations", []))
        for entry in entries:
            inherited.extend(entry["limitations"])

        substantive = claim_algebra.stable_unique(substantive)
        unregistered = [token for token in substantive if token not in known_tokens(profile)]
        _require(not unregistered, f"unregistered substantive token(s): {unregistered}")

        verdicts = profile["verdict_rules"]["verdicts"]
        return {
            "semantics_version": profile["semantics_version"],
            "verdict": (
                verdicts["default"]
                if asserted_supported and not counter_blocks and not substantive
                else verdicts["substantive"]
            ),
            "fatal_reasons": [],
            "target": value.get("target"),
            "asserted_claim": asserted,
            "asserted_claim_supported": asserted_supported,
            "support_entries": entries,
            "supported_claims": supported_claims,
            "maximal_supported_claims": maximal,
            "support_relations": [
                {"supported_claim": claim, "relation": claim_algebra.relation(profile, claim, asserted)}
                for claim in maximal
            ],
            "boundary_ceiling": ceiling,
            "boundary_grounding": boundary.get("grounding"),
            # Carried, never appraised: a recorder relation creates no base or
            # qualifier finding. Deduplicated by componentwise equality.
            "recorder_relations": claim_algebra.unique_relations(
                profile, value.get("recorder_relations") or []
            ),
            "substantive_reasons": substantive,
            "evaluation_gaps": claim_algebra.stable_unique(gap_tokens),
            "evaluation_gap_entries": gap_entries,
            "counter_evidence": copy.deepcopy(value.get("counter_evidence") or []),
            "inherited_limitations": claim_algebra.stable_unique(inherited),
            "evaluation_context": copy.deepcopy(value.get("evaluation_context")),
            # Carried, never interpreted.
            "evaluation_scope": copy.deepcopy(value.get("evaluation_scope")),
        }
    except (_Reject, claim_algebra.ClaimError) as exc:
        return {
            "engine_rejected": type(exc).__name__,
            "detail": str(exc),
        }


class _Engine:
    engine_id = ENGINE_ID
    implementation = IMPLEMENTATION

    def evaluate(self, vector: Vector, candidate: Candidate) -> dict[str, Any]:
        return evaluate(vector, candidate)


ENGINE = _Engine()
