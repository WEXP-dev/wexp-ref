"""Claim algebra — independent evaluator.

Classification: **ASSURANCE-CRITICAL — MUST REMAIN INDEPENDENT**

The structural partial order over qualified claims, the support relation, and
the fixed reject projection. These are the specification's algorithm and stay
in code; only the vocabulary they range over comes from the profile.

Written as explicit set comparisons over normalised (base, qualifiers) pairs.
The reference implementation derives the same relations by rank arithmetic over
an index table. Neither may import the other.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence


class ClaimError(ValueError):
    """Raised when a claim is not admissible under this profile."""


def normalise(profile: dict[str, Any], claim: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a claim and put its qualifiers into profile order."""

    bases = profile["orderings"]["base"]
    qualifiers_order = profile["orderings"]["qualifier"]
    base = claim.get("base")
    qualifiers = claim.get("qualifiers")
    if base not in bases:
        raise ClaimError(f"unknown content base: {base!r}")
    if not isinstance(qualifiers, list):
        raise ClaimError("claim qualifiers must be an array")
    if len(qualifiers) != len(set(qualifiers)):
        raise ClaimError("duplicate qualifier")
    unknown = set(qualifiers) - set(qualifiers_order)
    if unknown:
        raise ClaimError(f"unknown qualifier(s): {sorted(unknown)}")

    # The rule "a qualifier may be restricted to certain bases" is algorithm.
    # Which qualifier is restricted to which base is candidate vocabulary and
    # comes from the profile.
    admissibility = profile.get("qualifier_admissibility") or {}
    for qualifier in qualifiers:
        allowed = admissibility.get(qualifier)
        if allowed is not None and base not in allowed:
            raise ClaimError(f"qualifier {qualifier!r} does not apply to base {base!r}")

    ordered = sorted(qualifiers, key=qualifiers_order.index)
    return {"base": base, "qualifiers": ordered}


def key(profile: dict[str, Any], claim: Mapping[str, Any]) -> tuple[str, tuple[str, ...]]:
    normalised = normalise(profile, claim)
    return normalised["base"], tuple(normalised["qualifiers"])


def sort_key(profile: dict[str, Any], claim: Mapping[str, Any]) -> tuple[int, int, tuple[int, ...]]:
    bases = profile["orderings"]["base"]
    qualifiers_order = profile["orderings"]["qualifier"]
    normalised = normalise(profile, claim)
    ranks = tuple(qualifiers_order.index(q) for q in normalised["qualifiers"])
    return bases.index(normalised["base"]), len(ranks), ranks


def structurally_le(profile: dict[str, Any], lower: Mapping[str, Any], upper: Mapping[str, Any]) -> bool:
    """Section 4.5: ``(b1, A1) <= (b2, A2)`` iff ``b1 <= b2`` and ``A1`` is a
    subset of ``A2``.

    A product of the base order and qualifier inclusion. Both conjuncts are
    required, which is why ``(invocation, {IV})`` and ``(execution, {})`` are
    incomparable while ``(invocation, {IV})`` sits below ``(execution, {IV})``.
    """

    lower_base, lower_qualifiers = key(profile, lower)
    upper_base, upper_qualifiers = key(profile, upper)
    bases = profile["orderings"]["base"]
    return (
        bases.index(lower_base) <= bases.index(upper_base)
        and set(lower_qualifiers) <= set(upper_qualifiers)
    )


def dominates(profile: dict[str, Any], left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """Strict domination: ``right <= left`` and the two are not equal."""

    if key(profile, left) == key(profile, right):
        return False
    return structurally_le(profile, right, left)


def relation(profile: dict[str, Any], supported: Mapping[str, Any], asserted: Mapping[str, Any]) -> str:
    """Section 8.3, decided by the Section 4.5 order in both directions."""

    if key(profile, supported) == key(profile, asserted):
        return "equal"
    if structurally_le(profile, supported, asserted):
        return "support-below-claim"
    if structurally_le(profile, asserted, supported):
        return "support-above-claim"
    return "incomparable"


def maximal(profile: dict[str, Any], claims: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Those claims no other supported claim strictly dominates."""

    result: list[dict[str, Any]] = []
    for candidate in claims:
        if not any(dominates(profile, other, candidate) for other in claims if other is not candidate):
            result.append(normalise(profile, candidate))
    return sorted(result, key=lambda item: sort_key(profile, item))


def stable_unique(values: Iterable[str]) -> list[str]:
    """Union preserving first-seen order, used for limitations and reasons."""

    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def fixed_rejection(profile: dict[str, Any], fatal: Sequence[str]) -> dict[str, Any]:
    """The fixed reject projection: every field pinned, nothing inferred."""

    return {
        "semantics_version": profile["semantics_version"],
        "verdict": profile["verdict_rules"]["verdicts"]["fatal"],
        "fatal_reasons": list(fatal),
        "target": None,
        "asserted_claim": None,
        "asserted_claim_supported": False,
        "support_entries": [],
        "supported_claims": [],
        "maximal_supported_claims": [],
        "support_relations": [],
        "boundary_ceiling": None,
        "boundary_grounding": None,
        "recorder_relations": None,
        "substantive_reasons": [],
        "evaluation_gaps": [],
        "evaluation_gap_entries": [],
        "counter_evidence": None,
        "inherited_limitations": None,
        "evaluation_context": None,
        "evaluation_scope": None,
    }


def relation_key(profile: dict[str, Any], relation: Mapping[str, Any]) -> tuple[Any, ...]:
    """Identity of a recorder relation.

    Componentwise and total: two relations are equal only when every declared
    component is equal. Which components exist is candidate data; that the
    comparison is total is algorithm.
    """

    components = profile.get("recorder_relation_components")
    if not components:
        raise ClaimError("profile declares no recorder_relation_components")
    missing = [name for name in components if name not in relation]
    if missing:
        raise ClaimError(f"recorder relation is missing component(s): {sorted(missing)}")
    return tuple(_frozen(relation[name]) for name in components)


def _frozen(value: Any) -> Any:
    if isinstance(value, list):
        return ("[]", tuple(_frozen(v) for v in value))
    if isinstance(value, dict):
        return ("{}", tuple(sorted((k, _frozen(v)) for k, v in value.items())))
    return value


def unique_relations(profile: dict[str, Any], relations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """First-seen-order union under componentwise equality."""

    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    for relation in relations:
        key = relation_key(profile, relation)
        if key not in seen:
            seen.add(key)
            result.append(dict(relation))
    return result
