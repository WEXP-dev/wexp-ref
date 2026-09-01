"""Core ingress — independent evaluator.

Classification: **ASSURANCE-CRITICAL — MUST REMAIN INDEPENDENT**

The ordered rejection precedence a Core appraiser applies before any appraisal.
The order is normative and stays in code; only the token emitted at each
position comes from the profile.

Written as a list of guard callables evaluated in order, each returning either
``None`` or a ``(role, detail)`` pair. The reference implementation answers the
same question with a single-pass state machine. Neither may import the other.

A profile that does not declare the token for a position simply never reaches
it: if a guard fires and its role is undeclared, that is a hard failure, never
a silent pass.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Iterator

from wexp_ref.core01.harness.candidate import CandidateError, token_for


class IngressRejection(Exception):
    """An ordered ingress check rejected the input."""

    def __init__(self, role: str, detail: str) -> None:
        super().__init__(detail)
        self.role = role
        self.detail = detail


def _role_token(profile: dict[str, Any], role: str) -> str:
    try:
        return token_for(profile, role)
    except CandidateError as exc:
        raise IngressRejection(
            role, f"ingress position {role!r} reached but the profile declares no token"
        ) from exc


def _g_record_shape(profile: dict[str, Any], value: Any) -> tuple[str, str] | None:
    if not isinstance(value, dict):
        return ("malformed_normalized_input", "outer value is not an input record")
    version = value.get("semantics_version")
    if version is None or not isinstance(version, str):
        return ("malformed_normalized_input", "semantics_version absent or not a text atom")
    return None


def _g_semantics_version(profile: dict[str, Any], value: Any) -> tuple[str, str] | None:
    version = value.get("semantics_version")
    if version != profile["semantics_version"]:
        return (
            "unsupported_semantics_version",
            f"semantics_version {version!r} is not {profile['semantics_version']!r}",
        )
    return None


def _g_member_typing(profile: dict[str, Any], value: Any) -> tuple[str, str] | None:
    typed: dict[str, type | tuple[type, ...]] = {
        "base_findings": list,
        "qualifier_findings": list,
        "counter_evidence": list,
        "profile_evaluation_gaps": list,
        "inherited_limitations": list,
        "recorder_relations": list,
        "fatal_conditions": list,
        "asserted_claim": dict,
        "boundary_finding": dict,
        "evaluation_context": dict,
        "evaluation_scope": dict,
    }
    for member, expected in typed.items():
        if member in value and not isinstance(value[member], expected):
            return (
                "malformed_normalized_input",
                f"member {member!r} has the wrong logical type",
            )
    return None


def _g_scope_contract(profile: dict[str, Any], value: Any) -> tuple[str, str] | None:
    """Exact target and context scope, one of the Section 6.2 position-4 families.

    Section 6: "The boundary finding, every base and qualifier aggregate, and
    every profile-gap entry have a target equal to the top-level target and an
    evaluation_context_ref equal to the top-level evaluation-context identifier.
    A foreign-scoped aggregate is not negative evidence for this appraisal; it
    violates the normalized-input cross-field contract and produces
    E_PROFILE_MAPPING_INVALID."

    The contract is a property of the whole input, so one conforming aggregate
    does not rescue an input that also carries a foreign-scoped one.
    """

    scope = (value.get("target"), (value.get("evaluation_context") or {}).get("id"))
    groups = (("boundary finding", [value.get("boundary_finding") or {}]),
              ("base finding", value.get("base_findings") or []),
              ("qualifier finding", value.get("qualifier_findings") or []),
              ("profile gap entry", value.get("profile_evaluation_gaps") or []))
    for label, records in groups:
        for record in records:
            if (record.get("target"), record.get("evaluation_context_ref")) != scope:
                return ("profile_mapping_invalid",
                        f"a {label} is scoped to another target or evaluation context")
    return None


def _g_cross_field(profile: dict[str, Any], value: Any) -> tuple[str, str] | None:
    """Cross-field invariants, including the supplied-fatal category rule."""

    registry = profile["token_registry"]
    supplied = registry.get("supplied_fatal")
    derived = set(registry.get("derived_only") or ())
    declared = set(supplied or ())
    for token in value.get("fatal_conditions") or []:
        if not isinstance(token, str):
            return ("profile_mapping_invalid", "fatal_conditions member is not a token")
        if token in derived:
            return (
                "profile_mapping_invalid",
                f"{token} is appraiser-derived and invalid as a supplied fatal member",
            )
        if supplied is not None and token not in declared:
            return (
                "profile_mapping_invalid",
                f"{token} is not a permitted supplied fatal member",
            )
    return None


#: The ``wexp-core-1`` token registry as published in the Core document's IANA
#: table, by category. A Core token is bound to ``semantics_version`` and never
#: resolves through an applied registry; every other token is non-Core and must
#: resolve under the successor's cardinality-one procedure.
CORE_TOKENS_BY_CATEGORY: dict[str, frozenset[str]] = {
    "fatal": frozenset({
        "E_MALFORMED_NORMALIZED_INPUT", "E_UNSUPPORTED_SEMANTICS_VERSION",
        "E_CLAIM_OUT_OF_DOMAIN", "E_UNKNOWN_CRITICAL_SEMANTIC", "E_INTEGRITY_INVALID",
        "E_BINDING_MISMATCH", "E_PROFILE_MAPPING_INVALID", "E_CHAIN_DESCRIPTION_INVALID",
    }),
    "substantive": frozenset({
        "E_CHAIN_UNBOUND", "E_SHARED_VERIFICATION_ROOT", "E_BASE_EXCEEDS_BOUNDARY",
        "E_BOUNDARY_NOT_SUPPORTED", "E_EXACT_CLAIM_NOT_SUPPORTED",
        "E_MISSING_REQUIRED_EVIDENCE", "E_EVIDENCE_NOT_BOUND", "E_EVIDENCE_COVERAGE_MISMATCH",
        "E_PROV_NOT_SUPPORTED", "E_IV_NOT_SUPPORTED", "E_COUNTER_EVIDENCE_UNRESOLVED",
        "E_COUNTER_EVIDENCE_DEFEATING", "E_COMPOSITION_WARRANT_MISSING",
        "E_INDEPENDENCE_NOT_ESTABLISHED",
    }),
    "evaluation-gap": frozenset({
        "E_BASE_NOT_EVALUATED", "E_BOUNDARY_NOT_EVALUATED", "E_PROV_NOT_EVALUATED",
        "E_IV_NOT_EVALUATED", "E_COMPOSITION_NOT_EVALUATED", "E_COUNTER_EVIDENCE_NOT_EVALUATED",
    }),
}
CORE_TOKENS: frozenset[str] = frozenset().union(*CORE_TOKENS_BY_CATEGORY.values())

#: Contract identities under which the successor position-4 families apply.
#: The published Core-01 fixture table is normative for its own identity and its
#: fixture C14 contradicts the scope-consistency text (WCR2V-001 known issue C1,
#: repaired by the successor), so an engine faithful to both objects must key the
#: two families on the contract it is appraising under. Keyed by the descriptor's
#: authority.snapshot_id, which the loader binds to the bundled specification
#: bytes.
SUCCESSOR_CONTRACT_IDS: frozenset[str] = frozenset({
    "draft-sergeev-wexp-core-successor-candidate-001",
})


def successor_rules_apply(candidate: Any) -> bool:
    return getattr(candidate, "snapshot_id", None) in SUCCESSOR_CONTRACT_IDS


#: Which evaluation-scope capability governs a qualifier aggregate.
_QUALIFIER_CAPABILITY = {"PROV": "provenance-support", "IV": "independent-verification"}


def _governed_statuses(value: Any) -> Iterator[tuple[str, str, Any]]:
    """Every governed status field as ``(capability, field, status)``.

    Section "Core Conformance and Evaluation Scope" names the governed fields:
    every finding's target_binding for ``target-binding``; boundary status,
    binding and grounding for ``boundary-grounding``; a base aggregate's binding
    and semantic status for that base's support capability; PROV binding and
    semantic status for ``provenance-support``; IV binding, semantic and
    independence status for ``independent-verification``; and counter-entry
    status for ``counter-evidence``.
    """

    boundary = value.get("boundary_finding") or {}
    yield "target-binding", "boundary_finding.target_binding", boundary.get("target_binding")
    yield "boundary-grounding", "boundary_finding.status", boundary.get("status")
    yield "boundary-grounding", "boundary_finding.target_binding", boundary.get("target_binding")
    yield "boundary-grounding", "boundary_finding.grounding", boundary.get("grounding")
    for finding in value.get("base_findings") or []:
        base = finding.get("base")
        capability = f"{base}-support"
        yield "target-binding", f"base_findings[{base}].target_binding", finding.get("target_binding")
        yield capability, f"base_findings[{base}].target_binding", finding.get("target_binding")
        yield capability, f"base_findings[{base}].semantic_validation", finding.get("semantic_validation")
    for finding in value.get("qualifier_findings") or []:
        qualifier = finding.get("qualifier")
        label = f"qualifier_findings[{qualifier}@{finding.get('qualified_base')}]"
        capability = _QUALIFIER_CAPABILITY.get(qualifier, f"{qualifier}-support")
        yield "target-binding", f"{label}.target_binding", finding.get("target_binding")
        yield capability, f"{label}.target_binding", finding.get("target_binding")
        yield capability, f"{label}.semantic_validation", finding.get("semantic_validation")
        if qualifier == "IV":
            yield capability, f"{label}.independence_validation", finding.get("independence_validation")
    for index, entry in enumerate(value.get("counter_evidence") or []):
        yield "counter-evidence", f"counter_evidence[{index}].status", entry.get("status")


def _g_scope_status(profile: dict[str, Any], value: Any) -> tuple[str, str] | None:
    """Scope/status consistency, a Section 6.2 position-4 family.

    "A scope value of evaluated with a governed not-evaluated status ... violates
    the cross-field contract and produces E_PROFILE_MAPPING_INVALID." A scope
    value of not-evaluated never violates; a capability the profile does not
    declare is unconstrained.
    """

    scope = value.get("evaluation_scope") or {}
    for capability, field, status in _governed_statuses(value):
        if status == "not-evaluated" and scope.get(capability) == "evaluated":
            return (
                "profile_mapping_invalid",
                f"{field} is not-evaluated while evaluation_scope[{capability!r}] is evaluated",
            )
    return None


def _use_sites(value: Any) -> Iterator[tuple[str, str, str]]:
    """Every supplied token as ``(required category, token, where)``."""

    for token in value.get("fatal_conditions") or []:
        yield "fatal", token, "fatal_conditions"
    for index, entry in enumerate(value.get("counter_evidence") or []):
        for token in entry.get("reasons") or []:
            yield "substantive", token, f"counter_evidence[{index}].reasons"
    for token in (value.get("boundary_finding") or {}).get("reasons") or []:
        yield "substantive", token, "boundary_finding.reasons"
    for finding in value.get("base_findings") or []:
        for token in finding.get("reasons") or []:
            yield "substantive", token, f"base_findings[{finding.get('base')}].reasons"
    for finding in value.get("qualifier_findings") or []:
        for token in finding.get("reasons") or []:
            yield "substantive", token, f"qualifier_findings[{finding.get('qualifier')}].reasons"
    for index, gap in enumerate(value.get("profile_evaluation_gaps") or []):
        token = gap.get("token")
        if token is not None:
            yield "evaluation-gap", token, f"profile_evaluation_gaps[{index}].token"


def _distinct_registries(references: list[Any]) -> list[dict[str, Any]]:
    """De-duplicate byte-identical registry references only (successor step 2)."""

    seen: dict[str, dict[str, Any]] = {}
    for reference in references:
        registry = (reference or {}).get("registry") or {}
        identity = json.dumps(registry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        seen.setdefault(identity, registry)
    return list(seen.values())


def resolve_non_core_tokens(profile: dict[str, Any], value: Any) -> tuple[tuple[str, str] | None, dict[str, Any]]:
    """Successor section "Non-Core Token Resolution", steps 1 to 5.

    Returns ``(failure, report)``. ``failure`` is a ``(role, detail)`` pair for
    the first token that does not resolve, else ``None``. ``report`` is a
    diagnostic ledger of what was enumerated, so that a positive result can be
    shown to rest on the registry references rather than on the profile's own
    token registry.

    When the evaluation context carries no ``registry_references`` the
    qualification profile's ``token_registry`` is the single applied registry
    and the predecessor behaviour (tokens checked against the profile) stands.
    """

    context = value.get("evaluation_context") or {}
    references = context.get("registry_references")
    if references is None:
        return None, {"mode": "single-applied-registry", "authority": "profile.token_registry"}
    if not isinstance(references, list):
        return ("profile_mapping_invalid", "registry_references is not a set"), {"mode": "invalid"}
    applied = set(context.get("profile_identifiers") or [])
    for reference in references:
        if (reference or {}).get("referenced_by") not in applied:
            return (
                "profile_mapping_invalid",
                "a registry reference is not bound to an applied profile identifier",
            ), {"mode": "invalid"}
    registries = _distinct_registries(references)
    report: dict[str, Any] = {
        "mode": "multi-registry",
        "references": len(references),
        "distinct_registries": len(registries),
        "tokens": {},
    }
    for category, token, where in _use_sites(value):
        if token in CORE_TOKENS:
            continue
        bindings = sorted(
            f"{registry.get('identity')}@{registry.get('revision')}:{binding.get('category')}"
            for registry in registries
            for binding in registry.get("bindings") or []
            if binding.get("token") == token
        )
        report["tokens"][token] = {
            "use_site": where,
            "required_category": category,
            "distinct_bindings": len(bindings),
            "bindings": bindings,
        }
        if not bindings:
            return ("profile_mapping_invalid", f"{token} at {where}: zero bindings across applied registries"), report
        if len(bindings) > 1:
            return ("profile_mapping_invalid", f"{token} at {where}: {len(bindings)} distinct bindings"), report
        if not bindings[0].endswith(f":{category}"):
            return ("profile_mapping_invalid", f"{token} at {where}: bound category is not {category}"), report
    return None, report


def _g_token_binding(profile: dict[str, Any], value: Any) -> tuple[str, str] | None:
    failure, _report = resolve_non_core_tokens(profile, value)
    return failure


#: Positions 1 to 4 of the normative order. Position 5 (a valid supplied fatal
#: set) and position 6 (an inadmissible asserted claim) are decided by the
#: engine after ingress, because both need the appraisal vocabulary.
GUARDS: tuple[Callable[[dict[str, Any], Any], tuple[str, str] | None], ...] = (
    _g_record_shape,
    _g_semantics_version,
    _g_member_typing,
    _g_scope_contract,
    _g_cross_field,
)


#: The successor's additional position-4 families, applied only under a
#: successor contract identity (see SUCCESSOR_CONTRACT_IDS).
SUCCESSOR_GUARDS: tuple[Callable[[dict[str, Any], Any], tuple[str, str] | None], ...] = (
    _g_scope_status,
    _g_token_binding,
)


def evaluate_order(
    profile: dict[str, Any], value: Any, *, successor: bool = False
) -> tuple[str, str] | None:
    """Return ``(token, detail)`` for the first failing position, else ``None``."""

    for guard in GUARDS + (SUCCESSOR_GUARDS if successor else ()):
        outcome = guard(profile, value)
        if outcome is not None:
            role, detail = outcome
            return _role_token(profile, role), detail
    return None
