"""Reference implementation — profile-driven path.

Classification: **ASSURANCE-CRITICAL — MUST REMAIN INDEPENDENT**

The second of two independent implementations. This one accumulates support as
an ordered list of records and re-scans it, where the independent evaluator
keys a dictionary by normalised claim and filters. Its claim algebra is mask
arithmetic; the other's is set comparison. Neither imports the other.

Fidelity rule for this path: it reproduces frozen Candidate-001 behaviour
including its deliberate absences — no recorder-relation appraisal, no
composition, no scope-dependent branching, no derivation of fatal conditions.
Those live in the successor-capability register.

It never reads a vector's expectation.
"""

from __future__ import annotations

import copy
from typing import Any

from wexp_ref.core01.harness.candidate import Candidate, Vector, known_tokens, token_for

from . import algebra, gate

ENGINE_ID = "reference"
IMPLEMENTATION = "reference implementation, ordered support-record accumulation, profile-driven"


class OutsideSlice(Exception):
    """Raised when an input is not admissible for this candidate."""


# Section 8.6 gives PROV and IV separate not-evaluated rows carrying distinct
# tokens. A profile registers whichever of them it implements, so the row is
# applied to the qualifier whose token the profile actually registered rather
# than to every qualifier: emitting the IV token for a PROV finding would report
# a row that did not fire.
_NOT_EVALUATED_ROW = {"PROV": "E_PROV_NOT_EVALUATED", "IV": "E_IV_NOT_EVALUATED"}


def _domain(profile: dict[str, Any], name: str) -> tuple[str, ...]:
    return tuple(profile["status_domains"].get(name) or ())


def _check(condition: bool, detail: str) -> None:
    if not condition:
        raise OutsideSlice(detail)


def _in_scope(value: dict[str, Any], finding: dict[str, Any]) -> bool:
    """Section 8.1: the finding names the same target and evaluation context as
    the appraisal input. Section 8.4 states it as a conjunct of the admission
    predicate itself: f.target == input.target and f.evaluation_context_ref ==
    input.evaluation_context.id. A finding scoped elsewhere describes a different
    appraisal and cannot contribute support to this one.
    """

    context = (value.get("evaluation_context") or {}).get("id")
    return (
        finding.get("target") == value.get("target")
        and finding.get("evaluation_context_ref") == context
    )


def _finding_admitted(
    profile: dict[str, Any], finding: dict[str, Any], value: dict[str, Any]
) -> bool:
    assessment = _domain(profile, "assessment")
    binding = finding.get("target_binding")
    validation = finding.get("semantic_validation")
    _check(binding in assessment, f"target_binding outside domain: {binding!r}")
    _check(validation in assessment, f"semantic_validation outside domain: {validation!r}")
    if not _in_scope(value, finding):
        return False
    return (binding, validation) == ("supported", "supported")


def _independence_satisfied(profile: dict[str, Any], qualifier: str, observed: Any) -> bool:
    requirements = profile.get("qualifier_independence") or {}
    if qualifier not in requirements:
        return True
    _check(observed in _domain(profile, "independence"), f"independence outside domain: {observed!r}")
    return observed == requirements[qualifier]


def _bears_on(profile: dict[str, Any], affected: Any, claim_list: list[dict[str, Any]]) -> bool:
    if affected == "all-admissible-claims":
        return True
    _check(isinstance(affected, list), "affected_claims must be an array or all-admissible-claims")
    targets = [algebra.encode(profile, item)[:2] for item in affected]
    return any(algebra.encode(profile, claim)[:2] in targets for claim in claim_list)


def evaluate(vector: Vector, candidate: Candidate) -> dict[str, Any]:
    profile = candidate.profile
    value = vector.input
    try:
        successor = gate.under_successor_contract(candidate)
        screened = gate.screen(profile, value, successor=True) if successor else gate.screen(profile, value)
        if screened is not None:
            token, _detail = screened
            return algebra.fixed_rejection(profile, [token])
        # Successor contracts carry the binding ledger as an audit field outside
        # the comparison; predecessor contracts keep the predecessor result bytes.
        audit: dict[str, Any] = (
            {"diagnostic_token_resolution": gate.binding_ledger(profile, value)[1]} if successor else {}
        )

        fatal = list(value.get("fatal_conditions") or [])
        if fatal:
            return algebra.fixed_rejection(profile, fatal)

        boundary = value.get("boundary_finding") or {}
        _check(boundary.get("status") == "supported", "boundary ceiling is not accepted")
        _check(boundary.get("target_binding") == "supported", "boundary ceiling is not target-bound")
        bases = profile["orderings"]["base"]
        _check(
            _in_scope(value, {"target": boundary.get("target"),
                              "evaluation_context_ref": boundary.get("evaluation_context_ref")}),
            "boundary finding is not scoped to the appraisal target and context",
        )
        ceiling = boundary.get("ceiling_base")
        _check(ceiling in bases, "accepted boundary lacks a valid ceiling")
        ceiling_rank = bases.index(ceiling)

        records: list[dict[str, Any]] = []
        seen: list[tuple[int, int]] = []
        substantive: list[str] = []
        over_ceiling_ranks: set[int] = set()
        present_bases: set[str] = set()
        present_qualifiers: dict[tuple[str, str], dict[str, Any]] = {}

        def remember(claim: dict[str, Any], basis: list[str], limits: list[str]) -> None:
            identity = algebra.encode(profile, claim)[:2]
            _check(identity not in seen, "duplicate semantic finding")
            seen.append(identity)
            records.append({"claim": claim, "basis_refs": basis, "limitations": limits})

        for finding in value.get("base_findings") or []:
            base = finding.get("base")
            _check(base in bases, "base finding uses an unknown base")
            if not _in_scope(value, finding):
                # Section 6: a foreign-scoped aggregate "is not negative evidence
                # for this appraisal". It is not part of this appraisal at all, so
                # it must not even count as a supplied aggregate — otherwise it
                # would suppress the Section 8.6 absence row for the aggregate
                # that is genuinely missing here.
                continue
            # Presence is not admission: Section 8.6 distinguishes an absent
            # aggregate from a present one whose status did not pass.
            present_bases.add(base)
            if not _finding_admitted(profile, finding, value):
                continue
            if bases.index(base) > ceiling_rank:
                # Section 8.6 assigns this row to the asserted-base aggregate.
                # Record the rank; whether it becomes a diagnostic is decided
                # once the asserted claim is known.
                over_ceiling_ranks.add(bases.index(base))
                continue
            remember(
                {"base": base, "qualifiers": []},
                algebra.union_in_order([*boundary.get("basis_refs", []), *finding.get("basis_refs", [])]),
                algebra.union_in_order([*boundary.get("limitations", []), *finding.get("limitations", [])]),
            )

        def find_record(base: str, qualifiers: list[str]) -> dict[str, Any] | None:
            wanted = algebra.encode(profile, {"base": base, "qualifiers": qualifiers})[:2]
            for record in records:
                if algebra.encode(profile, record["claim"])[:2] == wanted:
                    return record
            return None

        admitted_by_base: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for finding in value.get("qualifier_findings") or []:
            base = finding.get("qualified_base")
            qualifier = finding.get("qualifier")
            _check(base in bases, "qualifier finding uses an unknown base")
            _check(qualifier in profile["orderings"]["qualifier"], "qualifier finding uses an unknown qualifier")
            admitted = _finding_admitted(profile, finding, value) and _independence_satisfied(
                profile, qualifier, finding.get("independence_validation")
            )
            if not _in_scope(value, finding):
                continue
            present_qualifiers[(base, qualifier)] = finding
            parent = find_record(base, [])
            if not admitted or parent is None:
                continue
            admitted_by_base.setdefault(base, []).append((qualifier, finding))

        # Section 8.1: A ranges over the subsets of the admitted qualifier set
        # Q(b). Enumerating one qualifier at a time cannot reach a state such as
        # (execution, {PROV, IV}), which Section 4.4 admits.
        for base, contributions in admitted_by_base.items():
            parent = find_record(base, [])
            if parent is None:
                continue
            count = len(contributions)
            for mask in range(1, 1 << count):
                chosen = [contributions[i] for i in range(count) if mask & (1 << i)]
                names = sorted(q for q, _ in chosen)
                try:
                    claim = algebra.normalise(profile, {"base": base, "qualifiers": names})
                except algebra.ClaimRejected:
                    continue
                if algebra.encode(profile, claim)[:2] in seen:
                    continue
                remember(
                    claim,
                    algebra.union_in_order(
                        [*parent["basis_refs"], *[r for _, f in chosen for r in f.get("basis_refs", [])]]
                    ),
                    algebra.union_in_order(
                        [*parent["limitations"], *[l for _, f in chosen for l in f.get("limitations", [])]]
                    ),
                )

        entries = sorted(records, key=lambda record: algebra.sort_key(profile, record["claim"]))
        supported_claims = [record["claim"] for record in entries]
        maximal = algebra.maximal(profile, supported_claims)

        # Position 6: an inadmissible asserted claim is a normalized rejection,
        # never a leaked implementation exception.
        try:
            asserted = algebra.normalise(profile, value["asserted_claim"])
        except algebra.ClaimRejected:
            return algebra.fixed_rejection(
                profile, [token_for(profile, "claim_out_of_domain")]
            )
        asserted_identity = algebra.encode(profile, asserted)[:2]
        asserted_supported = asserted_identity in seen
        # Section 8.6, evaluated row by row for the rows this profile registers.
        # An absent aggregate triggers only its absence row, and a status row
        # requires that aggregate to be present, so a present aggregate can never
        # produce missing-required-evidence.
        missing = token_for(profile, "missing_required_evidence")
        row_fired = False
        if bases.index(asserted["base"]) in over_ceiling_ranks:
            substantive.append(token_for(profile, "base_exceeds_boundary"))
            row_fired = True
        if asserted["base"] not in present_bases:
            substantive.append(missing)
            row_fired = True
        for qualifier in asserted["qualifiers"]:
            if (asserted["base"], qualifier) not in present_qualifiers:
                substantive.append(missing)
                row_fired = True
        not_evaluated_row = token_for(profile, "qualifier_not_evaluated")
        qualifier_gaps: list[tuple[str, dict[str, Any]]] = []
        for qualifier in asserted["qualifiers"]:
            if _NOT_EVALUATED_ROW.get(qualifier) != not_evaluated_row:
                continue
            finding = present_qualifiers.get((asserted["base"], qualifier))
            if finding is None:
                continue
            if "not-evaluated" in (
                finding.get("target_binding"),
                finding.get("semantic_validation"),
                finding.get("independence_validation"),
            ):
                qualifier_gaps.append((not_evaluated_row, finding))
                row_fired = True
        # The ten Section 8.6 rows this profile does not register are a declared
        # absence, so a claim unsupported for one of their reasons still collapses
        # onto missing-required-evidence. That collapse is the fallback for rows
        # that cannot be named, not a rule: it applies only where no registered
        # row already said something exact.
        if not asserted_supported and not row_fired:
            substantive.append(missing)

        relevant = [asserted, *supported_claims]
        counter_domain = _domain(profile, "counter-evidence")

        gap_tokens: list[str] = []
        gap_entries: list[dict[str, Any]] = []
        inherited = list(value.get("inherited_limitations") or [])

        # A blocking status scoped to the asserted claim, per Section 8.2. An
        # entry aimed at a different claim never changes this claim's status.
        BLOCKING = {"not-evaluated", "unresolved-material", "defeating"}
        TOKEN_FOR_STATUS = {
            "unresolved-material": "counter_evidence_unresolved",
            "defeating": "counter_evidence_defeating",
        }
        counter_blocks = False
        for counter in value.get("counter_evidence") or []:
            status = counter.get("status")
            _check(status in counter_domain, f"counter status outside this candidate: {status!r}")
            if status not in BLOCKING:
                continue
            if not _bears_on(profile, counter.get("affected_claims"), [asserted]):
                continue
            counter_blocks = True
            for limitation in counter.get("limitations", []):
                inherited.append(limitation)
            # Core status token first, as the normative vector table renders it.
            if status in TOKEN_FOR_STATUS:
                substantive.append(token_for(profile, TOKEN_FOR_STATUS[status]))
            for reason in counter.get("reasons", []):
                substantive.append(reason)
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

        for token, finding in qualifier_gaps:
            gap_tokens.append(token)
            gap_entries.append(
                {
                    "token": token,
                    "target": value.get("target"),
                    "evaluation_context_ref": (value.get("evaluation_context") or {}).get("id"),
                    "affected_claims": [copy.deepcopy(asserted)],
                    "basis_refs": list(finding.get("basis_refs", [])),
                    "limitations": list(finding.get("limitations", [])),
                }
            )
            # Section 8.1: limitations on a finding that determines a gap for the
            # asserted claim join the inherited union.
            inherited.extend(finding.get("limitations", []))

        registered = tuple(profile["token_registry"]["classes"]["gap"])
        for gap in value.get("profile_evaluation_gaps") or []:
            _check(gap.get("token") in registered, "unregistered profile gap token")
            if not _bears_on(profile, gap.get("affected_claims"), relevant):
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

        # Section 8.1 union: boundary limitations and every support-entry
        # limitation join the input's inherited set and the applicable entries'.
        for limitation in boundary.get("limitations", []):
            inherited.append(limitation)
        for record in entries:
            for limitation in record["limitations"]:
                inherited.append(limitation)

        substantive = algebra.union_in_order(substantive)
        for token in substantive:
            _check(token in known_tokens(profile), f"unregistered substantive token: {token!r}")

        verdicts = profile["verdict_rules"]["verdicts"]
        return {
            "semantics_version": profile["semantics_version"],
            "verdict": (
                verdicts["default"]
                # Section 8.4 / Verdict: exact support plus counter-evidence not
                # blocking. A non-empty diagnostic set is not a third condition.
                if asserted_supported and not counter_blocks
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
                {"supported_claim": claim, "relation": algebra.relation(profile, claim, asserted)}
                for claim in maximal
            ],
            "boundary_ceiling": ceiling,
            "boundary_grounding": boundary.get("grounding"),
            # Carried, not appraised. Componentwise equality governs uniqueness.
            "recorder_relations": algebra.distinct_relations(
                profile, value.get("recorder_relations") or []
            ),
            "substantive_reasons": substantive,
            "evaluation_gaps": algebra.union_in_order(gap_tokens),
            "evaluation_gap_entries": gap_entries,
            "counter_evidence": copy.deepcopy(value.get("counter_evidence") or []),
            "inherited_limitations": algebra.union_in_order(inherited),
            "evaluation_context": copy.deepcopy(value.get("evaluation_context")),
            "evaluation_scope": copy.deepcopy(value.get("evaluation_scope")),
            **audit,
        }
    except (OutsideSlice, algebra.ClaimRejected, gate.GateRefusal) as exc:
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
