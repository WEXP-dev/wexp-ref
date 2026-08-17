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


def screen(profile: dict[str, Any], value: Any) -> tuple[str, str] | None:
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

    # 4. cross-field invariants, including the supplied-fatal category rule
    position = 4
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

    assert position == 4  # every position was visited in order
    return None
