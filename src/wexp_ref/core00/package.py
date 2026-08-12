"""Execute an exact Core -00 candidate vector package deterministically."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NoReturn

from wexp_ref.core00.evaluator import Core00InputError, evaluate
from wexp_ref.locks import validate_vectors_lock

_CORE_SPECIFICATION = {
    "document": "draft-sergeev-wexp-core",
    "revision": "00",
    "artifact": "xml",
    "sha256": "6cd8b680059cc81e1ec4c84737d9319ee242ef63e89c57de497bd57ede08d810",
}
_TEST_REPRESENTATION = {
    "id": "wexp-core-00-test-harness",
    "revision": "1",
    "status": "non-normative-test-representation",
}
_VECTOR_FIELDS = {
    "vector_id",
    "specification",
    "requirement_ids",
    "purpose",
    "classification",
    "test_representation",
    "input",
    "expected",
    "derivation",
}
_VECTOR_ID = re.compile(r"^WEXP-CORE-00-V[0-9]{4,}$")
_REQUIREMENT_ID = re.compile(r"^WEXP-CORE-00-REQ-[0-9]{4,}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PackageError(ValueError):
    """The pinned vector package is missing, altered, or outside this slice."""


def _fail(message: str) -> NoReturn:
    raise PackageError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                _fail(f"duplicate JSON member {key!r} in {path}")
            result[key] = value
        return result

    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream, object_pairs_hook=reject_duplicates)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot read JSON {path}: {exc}")


def _safe_file(root: Path, relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative:
        _fail(f"{label} must be a non-empty relative path")
    lexical = root / relative
    current = root
    for part in Path(relative).parts:
        current /= part
        if current.is_symlink():
            _fail(f"{label} must not traverse a symbolic link: {relative}")
    candidate = lexical.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        _fail(f"{label} escapes the vector package")
    if not candidate.is_file():
        _fail(f"{label} does not name a file: {relative}")
    return candidate


def _integrity_entry(root: Path, value: Any, label: str) -> None:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object")
    path = _safe_file(root, value.get("path"), f"{label}.path")
    digest = value.get("sha256")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        _fail(f"{label}.sha256 must be lowercase SHA-256 hex")
    if _sha256(path) != digest:
        _fail(f"{label} SHA-256 mismatch: {value.get('path')}")


def _vector(value: Any, manifest_item: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _VECTOR_FIELDS:
        _fail("candidate vector has missing or unknown top-level members")
    vector_id = value["vector_id"]
    if not isinstance(vector_id, str) or _VECTOR_ID.fullmatch(vector_id) is None:
        _fail("candidate vector_id is outside the Core -00 namespace")
    if vector_id != manifest_item.get("vector_id"):
        _fail(f"manifest identity does not match {vector_id}")
    if value["specification"] != _CORE_SPECIFICATION:
        _fail(f"{vector_id} does not bind the canonical Core -00 XML")
    if value["test_representation"] != _TEST_REPRESENTATION:
        _fail(f"{vector_id} does not use frozen harness revision 1")
    requirements = value["requirement_ids"]
    if (
        not isinstance(requirements, list)
        or not requirements
        or not all(
            isinstance(item, str) and _REQUIREMENT_ID.fullmatch(item) is not None
            for item in requirements
        )
        or len(requirements) != len(set(requirements))
    ):
        _fail(f"{vector_id} has invalid requirement_ids")
    classification = value["classification"]
    if not isinstance(classification, str) or classification not in {
        "positive",
        "negative",
        "boundary",
    }:
        _fail(f"{vector_id} has an unsupported classification")
    if classification != manifest_item.get("classification"):
        _fail(f"manifest classification does not match {vector_id}")
    if not isinstance(value["purpose"], str) or not value["purpose"]:
        _fail(f"{vector_id} purpose must be a non-empty string")
    if not isinstance(value["expected"], Mapping):
        _fail(f"{vector_id} expected result must be an object")
    if not isinstance(value["derivation"], Mapping):
        _fail(f"{vector_id} derivation must be an object")
    return value


def run_package(root: str | Path, lock: Any) -> dict[str, Any]:
    """Run all candidate Core -00 vectors named by an exact validated lock."""

    package_root = Path(root).resolve()
    if not package_root.is_dir():
        _fail(f"vector package root is not a directory: {package_root}")
    lock_result = validate_vectors_lock(lock)
    if lock_result["status"] != "VALID_PINNED_CANDIDATE":
        _fail("vector package requires a valid exact candidate lock")

    manifest_path = _safe_file(package_root, lock["manifest_path"], "manifest_path")
    manifest_digest = _sha256(manifest_path)
    if manifest_digest != lock["manifest_sha256"]:
        _fail("vector manifest SHA-256 does not match the dependency lock")
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, Mapping):
        _fail("vector manifest must be an object")
    if manifest.get("manifest_version") != 2:
        _fail("vector manifest_version must be 2")
    if manifest.get("manifest_kind") != "wexp-vector-integrity-index":
        _fail("unexpected vector manifest_kind")
    if manifest.get("release_status") != "candidate":
        _fail("the pinned package must remain explicitly candidate")
    if manifest.get("vector_category") != "specification-derived-test-vectors":
        _fail("unexpected vector category")
    schemas = manifest.get("schemas")
    if not isinstance(schemas, Mapping):
        _fail("manifest schemas must be an object")
    for name, entry in schemas.items():
        _integrity_entry(package_root, entry, f"schema {name}")
    requirements = manifest.get("requirements")
    if requirements:
        _integrity_entry(package_root, requirements, "requirements")
    manifest_vectors = manifest.get("vectors")
    if not isinstance(manifest_vectors, list):
        _fail("manifest vectors must be an array")

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for manifest_item_value in manifest_vectors:
        if not isinstance(manifest_item_value, Mapping):
            _fail("manifest vector entry must be an object")
        path = _safe_file(package_root, manifest_item_value.get("path"), "vector path")
        digest = _sha256(path)
        if digest != manifest_item_value.get("sha256"):
            _fail(f"vector SHA-256 mismatch: {manifest_item_value.get('path')}")
        if manifest_item_value.get("status") != "candidate":
            continue
        vector = _vector(_read_json(path), manifest_item_value)
        vector_id = vector["vector_id"]
        if vector_id in seen:
            _fail(f"duplicate vector_id: {vector_id}")
        seen.add(vector_id)
        try:
            observed = evaluate(vector["input"])
        except Core00InputError as exc:
            _fail(f"{vector_id} input is outside the frozen harness: {exc}")
        expected = dict(vector["expected"])
        results.append(
            {
                "vector_id": vector_id,
                "vector_path": manifest_item_value["path"],
                "vector_sha256": digest,
                "classification": vector["classification"],
                "requirement_ids": list(vector["requirement_ids"]),
                "parsing_result": "accepted",
                "expected": expected,
                "observed": observed,
                "result": "AGREE" if observed == expected else "DISAGREE",
            }
        )
    if not results:
        _fail("manifest contains no candidate Core -00 vectors")
    disagreements = sum(item["result"] == "DISAGREE" for item in results)
    return {
        "record_kind": "wexp-ref-core-00-slice-results",
        "record_version": 1,
        "implementation": "wexp-ref",
        "specification": dict(_CORE_SPECIFICATION),
        "vector_package": {
            "repository": lock["repository"],
            "commit": lock["commit"],
            "manifest_path": lock["manifest_path"],
            "manifest_sha256": manifest_digest,
            "package_status": "candidate",
            "vector_category": "specification-derived-test-vectors",
        },
        "summary": {
            "total": len(results),
            "agree": len(results) - disagreements,
            "disagree": disagreements,
            "status": "PASS" if disagreements == 0 else "FAIL",
        },
        "results": results,
        "claims": [
            "wexp-ref produced the expected result for each vector classified AGREE."
        ],
        "non_claims": [
            "This result does not establish complete Core -00 correctness.",
            "This result does not establish WEXP conformance beyond the tested slice.",
            "This result does not establish independent external interoperability.",
            "This result does not establish IETF acceptance.",
            "The vector package is a candidate, not a released or normative package.",
            "Agreement does not make this implementation authoritative.",
        ],
    }
