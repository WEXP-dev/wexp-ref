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

from typing import Any, Callable

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


#: Positions 1 to 4 of the normative order. Position 5 (a valid supplied fatal
#: set) and position 6 (an inadmissible asserted claim) are decided by the
#: engine after ingress, because both need the appraisal vocabulary.
GUARDS: tuple[Callable[[dict[str, Any], Any], tuple[str, str] | None], ...] = (
    _g_record_shape,
    _g_semantics_version,
    _g_member_typing,
    _g_cross_field,
)


def evaluate_order(profile: dict[str, Any], value: Any) -> tuple[str, str] | None:
    """Return ``(token, detail)`` for the first failing position, else ``None``."""

    for guard in GUARDS:
        outcome = guard(profile, value)
        if outcome is not None:
            role, detail = outcome
            return _role_token(profile, role), detail
    return None
