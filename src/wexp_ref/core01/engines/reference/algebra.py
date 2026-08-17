"""Claim algebra — reference implementation.

Classification: **ASSURANCE-CRITICAL — MUST REMAIN INDEPENDENT**

The same specified relations as the independent evaluator's claim algebra,
derived differently on purpose. This implementation encodes a claim as a base
rank plus a qualifier bitmask and answers domination and the support relation
with mask arithmetic, where the independent evaluator uses set comparison over
tuples. Agreement between the two is the evidence; a shared implementation
would destroy it.

Only vocabulary comes from the profile: base order, qualifier order, and which
qualifier is admissible on which base. The relations themselves are algorithm
and stay here.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

EQUAL = "equal"
ABOVE = "support-above-claim"
BELOW = "support-below-claim"
INCOMPARABLE = "incomparable"


class ClaimRejected(ValueError):
    """Raised when a claim is not admissible under this profile."""


def _qualifier_bit(profile: dict[str, Any], qualifier: str) -> int:
    order = profile["orderings"]["qualifier"]
    try:
        return 1 << order.index(qualifier)
    except ValueError as exc:
        raise ClaimRejected(f"unknown qualifier: {qualifier!r}") from exc


def encode(profile: dict[str, Any], claim: Mapping[str, Any]) -> tuple[int, int, tuple[str, ...]]:
    """Encode a claim as (base rank, qualifier mask, ordered qualifiers)."""

    bases = profile["orderings"]["base"]
    order = profile["orderings"]["qualifier"]
    base = claim.get("base")
    qualifiers = claim.get("qualifiers")
    if base not in bases:
        raise ClaimRejected(f"unknown content base: {base!r}")
    if not isinstance(qualifiers, list):
        raise ClaimRejected("claim qualifiers must be an array")

    mask = 0
    for qualifier in qualifiers:
        bit = _qualifier_bit(profile, qualifier)
        if mask & bit:
            raise ClaimRejected(f"duplicate qualifier: {qualifier!r}")
        mask |= bit

    # Rule in code, mapping in data: a qualifier may be restricted to a set of
    # bases, and which restriction applies is candidate vocabulary.
    restrictions = profile.get("qualifier_admissibility") or {}
    for qualifier in qualifiers:
        permitted = restrictions.get(qualifier)
        if permitted is not None and base not in permitted:
            raise ClaimRejected(f"qualifier {qualifier!r} does not apply to base {base!r}")

    ordered = tuple(name for name in order if mask & _qualifier_bit(profile, name))
    return bases.index(base), mask, ordered


def normalise(profile: dict[str, Any], claim: Mapping[str, Any]) -> dict[str, Any]:
    rank, _, ordered = encode(profile, claim)
    return {"base": profile["orderings"]["base"][rank], "qualifiers": list(ordered)}


def sort_key(profile: dict[str, Any], claim: Mapping[str, Any]) -> tuple[int, int, tuple[int, ...]]:
    rank, mask, ordered = encode(profile, claim)
    order = profile["orderings"]["qualifier"]
    return rank, bin(mask).count("1"), tuple(order.index(name) for name in ordered)


def _le(profile: dict[str, Any], lower: Mapping[str, Any], upper: Mapping[str, Any]) -> bool:
    """Section 4.5 as rank comparison plus mask containment.

    ``A1`` subset of ``A2`` is ``mask1 & mask2 == mask1``. Both conjuncts must
    hold; neither alone orders two claims.
    """

    lower_rank, lower_mask, _ = encode(profile, lower)
    upper_rank, upper_mask, _ = encode(profile, upper)
    return lower_rank <= upper_rank and (lower_mask & upper_mask) == lower_mask


def dominates(profile: dict[str, Any], left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    if encode(profile, left)[:2] == encode(profile, right)[:2]:
        return False
    return _le(profile, right, left)


def relation(profile: dict[str, Any], supported: Mapping[str, Any], asserted: Mapping[str, Any]) -> str:
    if encode(profile, supported)[:2] == encode(profile, asserted)[:2]:
        return EQUAL
    if _le(profile, supported, asserted):
        return BELOW
    if _le(profile, asserted, supported):
        return ABOVE
    return INCOMPARABLE


def maximal(profile: dict[str, Any], claims: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    keep: list[dict[str, Any]] = []
    for index, candidate in enumerate(claims):
        dominated = False
        for other_index, other in enumerate(claims):
            if other_index != index and dominates(profile, other, candidate):
                dominated = True
                break
        if not dominated:
            keep.append(normalise(profile, candidate))
    return sorted(keep, key=lambda item: sort_key(profile, item))


def union_in_order(values: Iterable[str]) -> list[str]:
    """First-seen-order union, used for limitations and reasons."""

    result: list[str] = []
    for value in values:
        if value not in result:
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


def _canonical(value: Any) -> str:
    """Order-stable rendering of one component, used only for comparison."""

    if isinstance(value, list):
        return "[" + ",".join(_canonical(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(f"{k}:{_canonical(v)}" for k, v in sorted(value.items())) + "}"
    return repr(value)


def relation_identity(profile: dict[str, Any], relation: Mapping[str, Any]) -> str:
    """Identity of a recorder relation, as a single canonical string.

    The independent evaluator builds a tuple key instead. Both must agree that
    equality is componentwise over every declared component and total.
    """

    components = profile.get("recorder_relation_components")
    if not components:
        raise ClaimRejected("profile declares no recorder_relation_components")
    parts = []
    for name in components:
        if name not in relation:
            raise ClaimRejected(f"recorder relation lacks component {name!r}")
        parts.append(f"{name}={_canonical(relation[name])}")
    return "|".join(parts)


def distinct_relations(profile: dict[str, Any], relations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """First-seen-order union under componentwise equality."""

    kept: list[dict[str, Any]] = []
    identities: list[str] = []
    for relation in relations:
        identity = relation_identity(profile, relation)
        if identity not in identities:
            identities.append(identity)
            kept.append(dict(relation))
    return kept
