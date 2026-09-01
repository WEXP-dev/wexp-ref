"""Core ingress — reference implementation.

Classification: **ASSURANCE-CRITICAL — MUST REMAIN INDEPENDENT**

The same normative rejection precedence as the independent evaluator's ingress,
derived differently. This one walks a single pass over a numbered position
table and returns at the first position that fails, where the independent
evaluator evaluates a list of guard callables. Neither imports the other.

The order is normative and stays in code. The token emitted at each position is
profile data, and reaching a position whose token the profile has not declared
is a hard failure rather than a silent pass.
"""

from __future__ import annotations

import json
from typing import Any

from wexp_ref.core01.harness.candidate import CandidateError, token_for

#: Members whose logical type is fixed by the normalized-input contract.
LIST_MEMBERS = (
    "base_findings",
    "qualifier_findings",
    "counter_evidence",
    "profile_evaluation_gaps",
    "inherited_limitations",
    "recorder_relations",
    "fatal_conditions",
)
OBJECT_MEMBERS = ("asserted_claim", "boundary_finding", "evaluation_context", "evaluation_scope")


class GateRefusal(Exception):
    """Raised when a position is reached whose token the profile omits."""


def _token(profile: dict[str, Any], role: str) -> str:
    try:
        return token_for(profile, role)
    except CandidateError as exc:
        raise GateRefusal(
            f"ingress position {role!r} reached but no token is declared for it"
        ) from exc


def screen(profile: dict[str, Any], value: Any, *, successor: bool = False) -> tuple[str, str] | None:
    """Single pass over the numbered positions; first failure returns.

    Positions 1–4 of the normative order. Positions 5 and 6 belong to the
    appraisal itself and are decided by the engine after this screen.
    """

    position = 0

    # 1. outer record and semantics_version atom
    position = 1
    if not isinstance(value, dict):
        return _token(profile, "malformed_normalized_input"), "outer value is not an input record"
    version = value.get("semantics_version")
    if not isinstance(version, str):
        return (
            _token(profile, "malformed_normalized_input"),
            "semantics_version absent or not a text atom",
        )

    # 2. version support, checked before any version-specific member rule
    position = 2
    expected = profile["semantics_version"]
    if version != expected:
        return (
            _token(profile, "unsupported_semantics_version"),
            f"semantics_version {version!r} is not {expected!r}",
        )

    # 3. version-specific member typing
    position = 3
    for member in LIST_MEMBERS:
        if member in value and not isinstance(value[member], list):
            return (
                _token(profile, "malformed_normalized_input"),
                f"member {member!r} is not a set",
            )
    for member in OBJECT_MEMBERS:
        if member in value and not isinstance(value[member], dict):
            return (
                _token(profile, "malformed_normalized_input"),
                f"member {member!r} is not an entry",
            )

    # 4. cross-field invariants. Section 6.2 names several families here; this
    #    engine implements exact target and context scope and the supplied-fatal
    #    category rule. Section 6 binds "the boundary finding, every base and
    #    qualifier aggregate, and every profile-gap entry" to the top-level target
    #    and evaluation-context identifier, and a foreign-scoped aggregate "is not
    #    negative evidence for this appraisal" -- it makes the whole input
    #    contract-invalid, before any claim is appraised.
    position = 4
    target = value.get("target")
    context = (value.get("evaluation_context") or {}).get("id")
    scoped = [("boundary_finding", [value.get("boundary_finding") or {}])]
    for member in ("base_findings", "qualifier_findings", "profile_evaluation_gaps"):
        scoped.append((member, value.get(member) or []))
    for member, records in scoped:
        for record in records:
            if record.get("target") != target or record.get("evaluation_context_ref") != context:
                return (
                    _token(profile, "profile_mapping_invalid"),
                    f"{member} entry is scoped to another target or evaluation context",
                )

    registry = profile["token_registry"]
    derived_only = tuple(registry.get("derived_only") or ())
    supplied_fatal = registry.get("supplied_fatal")
    for token in value.get("fatal_conditions") or []:
        if not isinstance(token, str):
            return (
                _token(profile, "profile_mapping_invalid"),
                "a fatal_conditions member is not a token",
            )
        if token in derived_only:
            return (
                _token(profile, "profile_mapping_invalid"),
                f"{token} is appraiser-derived and cannot be supplied",
            )
        if supplied_fatal is not None and token not in supplied_fatal:
            return (
                _token(profile, "profile_mapping_invalid"),
                f"{token} is outside the permitted supplied fatal category",
            )

    if not successor:
        assert position == 4  # every predecessor position was visited in order
        return None

    # 4c. scope/status consistency (successor contracts only, see
    #     SUCCESSOR_CONTRACTS). Section "Core Conformance and Evaluation Scope":
    #     a scope value of evaluated with a governed not-evaluated status
    #     violates the cross-field contract. One pass collects every governed
    #     (capability, status) row into a table, then the table is screened.
    scope = value.get("evaluation_scope") or {}
    governed: list[tuple[str, str, Any]] = []
    boundary = value.get("boundary_finding") or {}
    governed.append(("target-binding", "boundary_finding.target_binding", boundary.get("target_binding")))
    for field in ("status", "target_binding", "grounding"):
        governed.append(("boundary-grounding", f"boundary_finding.{field}", boundary.get(field)))
    for record in value.get("base_findings") or []:
        capability = f"{record.get('base')}-support"
        governed.append(("target-binding", f"base_findings[{record.get('base')}].target_binding", record.get("target_binding")))
        for field in ("target_binding", "semantic_validation"):
            governed.append((capability, f"base_findings[{record.get('base')}].{field}", record.get(field)))
    for record in value.get("qualifier_findings") or []:
        qualifier = record.get("qualifier")
        capability = QUALIFIER_CAPABILITY.get(qualifier, f"{qualifier}-support")
        label = f"qualifier_findings[{qualifier}@{record.get('qualified_base')}]"
        governed.append(("target-binding", f"{label}.target_binding", record.get("target_binding")))
        fields = ("target_binding", "semantic_validation", "independence_validation") if qualifier == "IV" \
            else ("target_binding", "semantic_validation")
        for field in fields:
            governed.append((capability, f"{label}.{field}", record.get(field)))
    for index, record in enumerate(value.get("counter_evidence") or []):
        governed.append(("counter-evidence", f"counter_evidence[{index}].status", record.get("status")))
    for capability, field, status in governed:
        if scope.get(capability) == "evaluated" and status == "not-evaluated":
            return (
                _token(profile, "profile_mapping_invalid"),
                f"evaluation_scope[{capability!r}] is evaluated but {field} is not-evaluated",
            )

    # 4d. non-Core token binding across the applied registries (successor
    #     section "Non-Core Token Resolution"). Built as a lookup table from the
    #     de-duplicated registry set, then each use site is checked against it.
    outcome, _ledger = binding_ledger(profile, value)
    if outcome is not None:
        return outcome

    assert position == 4  # every position was visited in order
    return None


#: The published wexp-core-1 token registry (IANA table), as (token, category)
#: rows. Core tokens bind to semantics_version; they are never resolved through
#: an applied registry.
CORE_REGISTRY: tuple[tuple[str, str], ...] = (
    ("E_MALFORMED_NORMALIZED_INPUT", "fatal"),
    ("E_UNSUPPORTED_SEMANTICS_VERSION", "fatal"),
    ("E_CLAIM_OUT_OF_DOMAIN", "fatal"),
    ("E_UNKNOWN_CRITICAL_SEMANTIC", "fatal"),
    ("E_INTEGRITY_INVALID", "fatal"),
    ("E_BINDING_MISMATCH", "fatal"),
    ("E_PROFILE_MAPPING_INVALID", "fatal"),
    ("E_CHAIN_DESCRIPTION_INVALID", "fatal"),
    ("E_CHAIN_UNBOUND", "substantive"),
    ("E_SHARED_VERIFICATION_ROOT", "substantive"),
    ("E_BASE_EXCEEDS_BOUNDARY", "substantive"),
    ("E_BOUNDARY_NOT_SUPPORTED", "substantive"),
    ("E_EXACT_CLAIM_NOT_SUPPORTED", "substantive"),
    ("E_MISSING_REQUIRED_EVIDENCE", "substantive"),
    ("E_EVIDENCE_NOT_BOUND", "substantive"),
    ("E_EVIDENCE_COVERAGE_MISMATCH", "substantive"),
    ("E_PROV_NOT_SUPPORTED", "substantive"),
    ("E_IV_NOT_SUPPORTED", "substantive"),
    ("E_COUNTER_EVIDENCE_UNRESOLVED", "substantive"),
    ("E_COUNTER_EVIDENCE_DEFEATING", "substantive"),
    ("E_COMPOSITION_WARRANT_MISSING", "substantive"),
    ("E_INDEPENDENCE_NOT_ESTABLISHED", "substantive"),
    ("E_BASE_NOT_EVALUATED", "evaluation-gap"),
    ("E_BOUNDARY_NOT_EVALUATED", "evaluation-gap"),
    ("E_PROV_NOT_EVALUATED", "evaluation-gap"),
    ("E_IV_NOT_EVALUATED", "evaluation-gap"),
    ("E_COMPOSITION_NOT_EVALUATED", "evaluation-gap"),
    ("E_COUNTER_EVIDENCE_NOT_EVALUATED", "evaluation-gap"),
)
CORE_TOKEN_CATEGORY: dict[str, str] = dict(CORE_REGISTRY)

#: The scope capability that governs each qualifier aggregate.
QUALIFIER_CAPABILITY = {"PROV": "provenance-support", "IV": "independent-verification"}

#: Contract identities whose position-4 screen includes the successor families.
#: The published Core-01 object keeps its predecessor screen because its own
#: normative fixture C14 contradicts the scope-consistency text (known issue C1,
#: repaired by the successor); the two cannot be satisfied under one identity.
SUCCESSOR_CONTRACTS: tuple[str, ...] = ("draft-sergeev-wexp-core-successor-candidate-001",)


def under_successor_contract(candidate: Any) -> bool:
    return getattr(candidate, "snapshot_id", None) in SUCCESSOR_CONTRACTS


def _registry_bytes(registry: Any) -> bytes:
    return json.dumps(registry, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def binding_ledger(profile: dict[str, Any], value: Any) -> tuple[tuple[str, str] | None, dict[str, Any]]:
    """Screen every supplied non-Core token against the applied registries.

    Returns ``(outcome, ledger)``: ``outcome`` is the ``(token, detail)`` pair for
    the first position that fails, else ``None``; ``ledger`` records the
    enumeration so a pass can be audited. Without ``registry_references`` the
    profile's own token registry is the single applied registry and the
    predecessor screening (profile membership, applied by the engine) stands.
    """

    context = value.get("evaluation_context") or {}
    references = context.get("registry_references")
    if references is None:
        return None, {"mode": "single-applied-registry", "authority": "profile.token_registry"}
    if not isinstance(references, list):
        return (_token(profile, "profile_mapping_invalid"), "registry_references is not a set"), {"mode": "invalid"}
    applied = tuple(context.get("profile_identifiers") or ())
    for reference in references:
        if (reference or {}).get("referenced_by") not in applied:
            return (
                _token(profile, "profile_mapping_invalid"),
                "registry reference made by a profile outside the applied set",
            ), {"mode": "invalid"}

    # Step 2: byte-identical registry references collapse to one row; anything
    # else stays distinct even when token and category coincide.
    distinct: dict[bytes, dict[str, Any]] = {}
    for reference in references:
        registry = (reference or {}).get("registry") or {}
        distinct.setdefault(_registry_bytes(registry), registry)

    # Step 1: enumerate every binding into a token -> rows table.
    table: dict[str, list[tuple[str, str, str]]] = {}
    for registry in distinct.values():
        for binding in registry.get("bindings") or []:
            row = (str(registry.get("identity")), str(registry.get("revision")), str(binding.get("category")))
            table.setdefault(str(binding.get("token")), []).append(row)

    ledger: dict[str, Any] = {
        "mode": "multi-registry",
        "references": len(references),
        "distinct_registries": len(distinct),
        "tokens": {},
    }
    sites: list[tuple[str, str, str]] = []
    for token in value.get("fatal_conditions") or []:
        sites.append(("fatal", token, "fatal_conditions"))
    for index, record in enumerate(value.get("counter_evidence") or []):
        for token in record.get("reasons") or []:
            sites.append(("substantive", token, f"counter_evidence[{index}].reasons"))
    for token in (value.get("boundary_finding") or {}).get("reasons") or []:
        sites.append(("substantive", token, "boundary_finding.reasons"))
    for record in value.get("base_findings") or []:
        for token in record.get("reasons") or []:
            sites.append(("substantive", token, f"base_findings[{record.get('base')}].reasons"))
    for record in value.get("qualifier_findings") or []:
        for token in record.get("reasons") or []:
            sites.append(("substantive", token, f"qualifier_findings[{record.get('qualifier')}].reasons"))
    for index, record in enumerate(value.get("profile_evaluation_gaps") or []):
        if record.get("token") is not None:
            sites.append(("evaluation-gap", record["token"], f"profile_evaluation_gaps[{index}].token"))

    # Steps 3 to 5: exactly one distinct row with the required category; order,
    # recency and provenance never break a tie because no tie is broken.
    for category, token, where in sites:
        if token in CORE_TOKEN_CATEGORY:
            continue
        rows = sorted(table.get(token, []))
        ledger["tokens"][token] = {
            "use_site": where,
            "required_category": category,
            "distinct_bindings": len(rows),
            "bindings": [f"{identity}@{revision}:{bound}" for identity, revision, bound in rows],
        }
        if len(rows) == 0:
            return (_token(profile, "profile_mapping_invalid"), f"{token} at {where}: no binding in any applied registry"), ledger
        if len(rows) > 1:
            return (_token(profile, "profile_mapping_invalid"), f"{token} at {where}: {len(rows)} distinct bindings"), ledger
        if rows[0][2] != category:
            return (_token(profile, "profile_mapping_invalid"), f"{token} at {where}: category {rows[0][2]} is not {category}"), ledger
    return None, ledger
