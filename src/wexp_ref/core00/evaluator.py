"""Evaluate the non-normative harness used by the first Core -00 slice.

This module does not parse a WEXP protocol record. It consumes only the
abstract facts fixed by revision 1 of the Core -00 test harness.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NoReturn

_LEVELS = ("WL0", "WL1", "WL2", "WL3", "WL4", "WL5")
_CAPABILITY_CEILING = {
    "CC0": 0,
    "CC1": 0,
    "CC2": 2,
    "CC3": 3,
    "CC4": 4,
    "CC5": 5,
}
_BOUNDARY_BASE = {
    "manual-approval": 1,
    "proxy": 2,
    "host-hook": 3,
}
_PRIOR_CHECKS = {
    "structure": "valid",
    "canonicalization": "valid",
    "timestamps": "valid",
    "signature": "valid",
    "key_binding": "valid",
    "capabilities_resolution": "accepted",
    "hash_algorithms": "supported",
    "recorder_qualification": "absent",
    "chain": "absent",
}
_EVIDENCE_FIELDS = {
    "arguments_hash",
    "execution_fields",
    "bound_provenance",
    "bound_independent_verification",
}
_INPUT_FIELDS = {
    "prior_checks",
    "boundary_type",
    "claimed_level",
    "effective_conformance_class",
    "evidence",
    "unknown_extensions",
}


class Core00InputError(ValueError):
    """The value is outside the frozen Core -00 harness contract."""


def _fail(message: str) -> NoReturn:
    raise Core00InputError(message)


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object")
    if not all(isinstance(key, str) for key in value):
        _fail(f"{label} member names must be strings")
    return value


def _exact_members(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        _fail(f"{label} members differ: missing={missing}, unknown={unknown}")


def _validated_input(value: Any) -> Mapping[str, Any]:
    item = _object(value, "input")
    _exact_members(item, _INPUT_FIELDS, "input")

    prior = _object(item["prior_checks"], "input.prior_checks")
    _exact_members(prior, set(_PRIOR_CHECKS), "input.prior_checks")
    for name, required in _PRIOR_CHECKS.items():
        if prior[name] != required:
            _fail(f"input.prior_checks.{name} must be {required!r}")

    boundary = item["boundary_type"]
    if boundary not in _BOUNDARY_BASE:
        _fail(
            "input.boundary_type is outside the first slice; supported values are "
            + ", ".join(sorted(_BOUNDARY_BASE))
        )
    claim = item["claimed_level"]
    if claim not in _LEVELS[1:]:
        _fail("input.claimed_level must be WL1 through WL5")
    capability = item["effective_conformance_class"]
    if capability not in _CAPABILITY_CEILING:
        _fail("input.effective_conformance_class must be CC0 through CC5")

    evidence = _object(item["evidence"], "input.evidence")
    _exact_members(evidence, _EVIDENCE_FIELDS, "input.evidence")
    for name in sorted(_EVIDENCE_FIELDS):
        if type(evidence[name]) is not bool:
            _fail(f"input.evidence.{name} must be a boolean")

    extensions = item["unknown_extensions"]
    if not isinstance(extensions, list):
        _fail("input.unknown_extensions must be an array")
    seen: set[tuple[str, bool]] = set()
    for index, extension_value in enumerate(extensions):
        extension = _object(extension_value, f"input.unknown_extensions[{index}]")
        _exact_members(extension, {"name", "critical"}, f"input.unknown_extensions[{index}]")
        name = extension["name"]
        if not isinstance(name, str) or not name or not name[0].islower() or not all(
            character.islower() or character.isdigit() or character == "-"
            for character in name
        ):
            _fail(f"input.unknown_extensions[{index}].name is invalid")
        if type(extension["critical"]) is not bool:
            _fail(f"input.unknown_extensions[{index}].critical must be a boolean")
        identity = (name, extension["critical"])
        if identity in seen:
            _fail("input.unknown_extensions must contain unique objects")
        seen.add(identity)
    return item


def _attainable(item: Mapping[str, Any]) -> int:
    """Return the highest slice level supported by boundary and evidence facts."""

    evidence = item["evidence"]
    boundary_base = _BOUNDARY_BASE[item["boundary_type"]]
    claim = _LEVELS.index(item["claimed_level"])
    supported = 0

    # Core -00 Section 7.1 evaluates each level only when it does not exceed
    # the claim and that level's own conditional fields are present. Higher
    # level fields therefore cannot satisfy a lower claim whose own fields are
    # absent.
    if claim >= 1 and boundary_base >= 1 and evidence["arguments_hash"]:
        supported = 1
    if claim >= 2 and boundary_base >= 2 and evidence["arguments_hash"]:
        supported = 2
    if claim >= 3 and boundary_base >= 3 and evidence["execution_fields"]:
        supported = 3
    if boundary_base >= 3 and evidence["execution_fields"]:
        if claim >= 4 and evidence["bound_provenance"]:
            supported = 4
        if claim >= 5 and evidence["bound_independent_verification"]:
            supported = 5
    return supported


def evaluate(value: Any) -> dict[str, Any]:
    """Evaluate one strict harness input and return its observable result."""

    item = _validated_input(value)
    if any(extension["critical"] for extension in item["unknown_extensions"]):
        return {
            "verdict": "reject",
            "errors": ["E_UNKNOWN_CRITICAL_EXTENSION"],
        }

    claimed = _LEVELS.index(item["claimed_level"])
    ceiling = _CAPABILITY_CEILING[item["effective_conformance_class"]]
    verified = min(claimed, _attainable(item), ceiling)
    return {
        "verdict": "accept" if verified == claimed else "downgrade",
        "verified_level": _LEVELS[verified],
    }
