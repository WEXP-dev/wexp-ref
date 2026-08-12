"""Validation for immutable cross-repository dependency locks."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FLOATING = {"head", "main", "master", "latest"}


def validate_vectors_lock(value: Any) -> dict[str, Any]:
    """Validate an immutable vector-package lock for this implementation."""

    errors: list[str] = []
    if not isinstance(value, Mapping):
        return {"status": "INVALID", "errors": ["lock must be an object"]}
    expected = {
        "lock_version",
        "dependency",
        "repository",
        "status",
        "package_status",
        "commit",
        "manifest_path",
        "manifest_sha256",
    }
    if set(value) != expected:
        errors.append("lock has missing or unknown members")
    if value.get("lock_version") != 2:
        errors.append("lock_version must be 2")
    if value.get("dependency") != "wexp-vectors":
        errors.append("dependency must be wexp-vectors")
    if value.get("repository") != "WEXP-dev/wexp-vectors":
        errors.append("repository must be WEXP-dev/wexp-vectors")
    if value.get("status") != "pinned":
        errors.append("status must be pinned")
    package_status = value.get("package_status")
    if package_status != "candidate":
        errors.append("package_status must be candidate")
    commit = value.get("commit")
    if not isinstance(commit, str) or _COMMIT.fullmatch(commit) is None:
        errors.append("commit must be an exact lowercase 40-hex object ID")
    manifest_path = value.get("manifest_path")
    if (
        not isinstance(manifest_path, str)
        or not manifest_path
        or manifest_path.startswith("/")
        or "\\" in manifest_path
        or ".." in manifest_path.split("/")
    ):
        errors.append("manifest_path must be a safe non-empty relative path")
    manifest_hash = value.get("manifest_sha256")
    if not isinstance(manifest_hash, str) or _SHA256.fullmatch(manifest_hash) is None:
        errors.append("manifest_sha256 must be lowercase SHA-256 hex")
    for item in value.values():
        if isinstance(item, str) and item.lower() in _FLOATING:
            errors.append(f"floating dependency identity is forbidden: {item}")
    if errors:
        return {"status": "INVALID", "errors": errors}
    return {
        "status": "VALID_PINNED_CANDIDATE",
        "errors": [],
        "immutable_identity_available": True,
        "package_status": package_status,
    }
