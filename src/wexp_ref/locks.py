"""Validation for immutable cross-repository dependency locks."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FLOATING = {"head", "main", "master", "latest"}


def validate_vectors_lock(value: Any) -> dict[str, Any]:
    """Validate a pinned lock or an explicit, non-passing blocked placeholder."""

    errors: list[str] = []
    if not isinstance(value, Mapping):
        return {"status": "INVALID", "errors": ["lock must be an object"]}
    common = {"lock_version", "dependency", "repository", "status"}
    if value.get("lock_version") != 1:
        errors.append("lock_version must be 1")
    if value.get("dependency") != "wexp-vectors":
        errors.append("dependency must be wexp-vectors")
    if not isinstance(value.get("repository"), str) or not value.get("repository"):
        errors.append("repository must be a non-empty string")
    status = value.get("status")
    if status == "pinned":
        allowed = common | {"commit", "manifest_sha256"}
        if set(value) != allowed:
            errors.append("pinned lock has missing or unknown members")
        commit = value.get("commit")
        if not isinstance(commit, str) or _COMMIT.fullmatch(commit) is None:
            errors.append("commit must be an exact lowercase 40-hex object ID")
        manifest_hash = value.get("manifest_sha256")
        if not isinstance(manifest_hash, str) or _SHA256.fullmatch(manifest_hash) is None:
            errors.append("manifest_sha256 must be lowercase SHA-256 hex")
    elif status == "blocked":
        allowed = common | {"blocked_reason", "required_resolution"}
        if set(value) != allowed:
            errors.append("blocked lock has missing or unknown members")
        for field in ("blocked_reason", "required_resolution"):
            if not isinstance(value.get(field), str) or not value[field]:
                errors.append(f"{field} must be a non-empty string")
        if any(name in value for name in ("commit", "revision", "ref")):
            errors.append("blocked lock must not carry a guessed revision")
    else:
        errors.append("status must be pinned or blocked")
    for item in value.values():
        if isinstance(item, str) and item.lower() in _FLOATING:
            errors.append(f"floating dependency identity is forbidden: {item}")
    if errors:
        return {"status": "INVALID", "errors": errors}
    return {
        "status": "VALID_PINNED" if status == "pinned" else "VALID_BLOCKED",
        "errors": [],
        "immutable_identity_available": status == "pinned",
    }
