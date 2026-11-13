"""Evidence-envelope tooling for external WEXP interoperability exercises.

This module is deliberately semantics-blind. It binds exact source materials,
neutral fixture bytes, and a frozen reading by digest; it does not infer or
compare protocol meaning.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SOURCE_LOCK_VERSION = "WEXP-INTEROP-SOURCE-LOCK-1"
COMMITMENT_VERSION = "WEXP-INTEROP-COMMITMENT-1"
VERIFICATION_VERSION = "WEXP-INTEROP-VERIFICATION-1"


class InteropError(ValueError):
    """An interoperability evidence artifact failed closed validation."""


def sha256_file(path: Path) -> str:
    """Hash the exact bytes of one file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    """Load UTF-8 JSON while rejecting duplicate object member names."""
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise InteropError(f"duplicate JSON member {key!r} in {path}")
            out[key] = value
        return out

    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream, object_pairs_hook=reject_duplicates)
    except UnicodeDecodeError as exc:
        raise InteropError(f"{path} is not UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise InteropError(f"invalid JSON in {path}: {exc}") from exc


def validate_source_lock(lock: Any) -> dict[str, Any]:
    """Validate the closed v1 source-lock shape without treating it as truth."""
    _exact_keys(lock, {"artifact_version", "repository", "git_commit", "materials", "non_claims"}, "source lock")
    if lock["artifact_version"] != SOURCE_LOCK_VERSION:
        raise InteropError("unsupported source lock artifact_version")
    if not isinstance(lock["repository"], str) or "/" not in lock["repository"]:
        raise InteropError("repository must be owner/name")
    if not isinstance(lock["git_commit"], str) or not GIT_SHA_RE.fullmatch(lock["git_commit"]):
        raise InteropError("git_commit must be a full 40-hex SHA")
    if not isinstance(lock["materials"], list) or not lock["materials"]:
        raise InteropError("materials must be a non-empty list")
    seen: set[str] = set()
    for item in lock["materials"]:
        _exact_keys(item, {"path", "sha256"}, "source material")
        path = item["path"]
        digest = item["sha256"]
        if not isinstance(path, str) or not path or path in seen or path.startswith("/") or ".." in Path(path).parts:
            raise InteropError("material path must be unique, relative, and traversal-free")
        seen.add(path)
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise InteropError(f"invalid sha256 for material {path}")
    if not isinstance(lock["non_claims"], list):
        raise InteropError("source lock non_claims must be a list")
    return lock


def verify_source_materials(lock: Any, source_root: Path) -> list[dict[str, str]]:
    """Verify selected source bytes against their locked digests."""
    lock = validate_source_lock(lock)
    root = source_root.resolve()
    results = []
    for item in lock["materials"]:
        path = (root / item["path"]).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise InteropError(f"material escapes source root: {item['path']}") from exc
        if not path.is_file():
            raise InteropError(f"missing source material: {item['path']}")
        actual = sha256_file(path)
        if actual != item["sha256"]:
            raise InteropError(f"source material digest mismatch: {item['path']}")
        results.append({"path": item["path"], "sha256": actual})
    return results


def prepare_commitment(source_lock_path: Path, fixtures_path: Path, reading_path: Path) -> dict[str, Any]:
    """Commit to exact artifact bytes; no JSON canonicalization is performed."""
    validate_source_lock(load_json(source_lock_path))
    _require_file(fixtures_path, "fixtures")
    _require_file(reading_path, "reading")
    return {
        "artifact_version": COMMITMENT_VERSION,
        "source_lock_sha256": sha256_file(source_lock_path),
        "fixtures_sha256": sha256_file(fixtures_path),
        "reading_sha256": sha256_file(reading_path),
        "hash_algorithm": "sha256",
        "commitment_scope": "exact-file-bytes",
        "non_claims": [
            "This commitment establishes only the digests of the named exact bytes.",
            "It does not establish semantic correctness of the reading.",
            "It does not establish author identity or independence by itself.",
        ],
    }


def verify_reveal(commitment: Any, source_lock_path: Path, fixtures_path: Path, reading_path: Path, source_root: Path) -> dict[str, Any]:
    """Verify a reveal and the selected source bytes against the frozen envelope."""
    _exact_keys(commitment, {"artifact_version", "source_lock_sha256", "fixtures_sha256", "reading_sha256", "hash_algorithm", "commitment_scope", "non_claims"}, "commitment")
    if commitment["artifact_version"] != COMMITMENT_VERSION:
        raise InteropError("unsupported commitment artifact_version")
    if commitment["hash_algorithm"] != "sha256" or commitment["commitment_scope"] != "exact-file-bytes":
        raise InteropError("unsupported commitment method")
    for field in ("source_lock_sha256", "fixtures_sha256", "reading_sha256"):
        if not isinstance(commitment[field], str) or not SHA256_RE.fullmatch(commitment[field]):
            raise InteropError(f"invalid {field}")

    actual = {"source_lock_sha256": sha256_file(source_lock_path), "fixtures_sha256": sha256_file(fixtures_path), "reading_sha256": sha256_file(reading_path)}
    mismatches = [field for field, digest in actual.items() if digest != commitment[field]]
    if mismatches:
        return {"artifact_version": VERIFICATION_VERSION, "status": "COMMITMENT_MISMATCH", "mismatches": mismatches, **actual, "non_claims": ["No semantic comparison was performed."]}

    lock = load_json(source_lock_path)
    materials = verify_source_materials(lock, source_root)
    return {
        "artifact_version": VERIFICATION_VERSION,
        "status": "VERIFIED",
        **actual,
        "repository": lock["repository"],
        "git_commit": lock["git_commit"],
        "verified_materials": materials,
        "non_claims": [
            "VERIFIED means the revealed bytes match the commitment and selected source bytes match the source lock.",
            "The git_commit is a pinned provenance identifier; this record does not by itself prove repository authorship or semantic truth.",
            "No semantic comparison was performed.",
        ],
    }


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise InteropError(f"missing {label} file: {path}")


def _exact_keys(value: Any, expected: set[str], where: str) -> None:
    if not isinstance(value, dict):
        raise InteropError(f"{where} must be an object")
    actual = set(value)
    if actual != expected:
        raise InteropError(f"{where} keys invalid; missing={sorted(expected-actual)}, extra={sorted(actual-expected)}")
