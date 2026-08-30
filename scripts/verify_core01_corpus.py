#!/usr/bin/env python3
"""Verify an exact wexp-vectors checkout and every locked Core-01 manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence


REQUIRED_CANDIDATES = frozenset(
    {
        "WEXP-CORE-01-VECTORS-001",
        "WEXP-CORE-01-VECTORS-002",
        "WEXP-CORE-01-VECTORS-003",
    }
)
REQUIRED_TOP_LEVEL = frozenset(
    {
        "lock_version",
        "dependency",
        "repository",
        "status",
        "package_status",
        "commit",
        "manifest_path",
        "manifest_sha256",
        "vector_sets",
    }
)
REQUIRED_SET_FIELDS = frozenset(
    {"candidate_id", "manifest_path", "manifest_sha256", "vector_set_sha256"}
)
HEX_40 = re.compile(r"[0-9a-f]{40}\Z")
HEX_64 = re.compile(r"[0-9a-f]{64}\Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_repository_path(value: object, *, field: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{field} must be a non-empty relative POSIX path")
    parsed = Path(value)
    if parsed.is_absolute() or ".." in parsed.parts:
        raise ValueError(f"{field} must stay inside the repository: {value}")
    return parsed


def validate_lock(lock: object) -> dict[str, object]:
    if not isinstance(lock, dict):
        raise ValueError("Core-01 lock must be a JSON object")
    if set(lock) != REQUIRED_TOP_LEVEL:
        raise ValueError("Core-01 lock has missing or unknown fields")
    if lock["lock_version"] != 3:
        raise ValueError(f"unsupported Core-01 lock_version: {lock['lock_version']!r}")
    expected_metadata = {
        "dependency": "wexp-vectors",
        "repository": "WEXP-dev/wexp-vectors",
        "status": "pinned",
    }
    for field, expected in expected_metadata.items():
        if lock[field] != expected:
            raise ValueError(f"Core-01 lock {field} must be {expected!r}")
    if lock["package_status"] != "candidate":
        raise ValueError("Core-01 lock package_status must be 'candidate'")
    if not isinstance(lock["commit"], str) or HEX_40.fullmatch(lock["commit"]) is None:
        raise ValueError("Core-01 lock commit must be a lowercase 40-hex object id")

    entries = lock["vector_sets"]
    if not isinstance(entries, list):
        raise ValueError("Core-01 lock must contain a vector_sets array")
    if len(entries) != len(REQUIRED_CANDIDATES):
        raise ValueError(
            f"Core-01 lock must contain exactly {len(REQUIRED_CANDIDATES)} vector-set entries"
        )
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("each vector_sets entry must be an object")
        if set(entry) != REQUIRED_SET_FIELDS:
            raise ValueError("vector_sets entry has missing or unknown fields")
        relative_repository_path(entry["manifest_path"], field="manifest_path")
        for field in ("manifest_sha256", "vector_set_sha256"):
            value = entry[field]
            if not isinstance(value, str) or HEX_64.fullmatch(value) is None:
                raise ValueError(f"{field} must be a lowercase 64-hex SHA-256 digest")

    candidates = [entry["candidate_id"] for entry in entries]
    if set(candidates) != REQUIRED_CANDIDATES or len(set(candidates)) != len(candidates):
        raise ValueError(
            "Core-01 lock must bind exactly: " + ", ".join(sorted(REQUIRED_CANDIDATES))
        )
    set_001 = next(
        entry for entry in entries if entry["candidate_id"] == "WEXP-CORE-01-VECTORS-001"
    )
    if (
        lock["manifest_path"] != set_001["manifest_path"]
        or lock["manifest_sha256"] != set_001["manifest_sha256"]
    ):
        raise ValueError("top-level manifest identity must match Set 001")
    return lock


def verify_manifest_artifacts(repository: Path, document: dict[str, object]) -> int:
    artifacts = document.get("artifacts")
    schemas = document.get("schemas")
    if not isinstance(artifacts, list) or not isinstance(schemas, dict):
        raise ValueError("manifest artifacts must be an array and schemas must be an object")

    bindings = list(artifacts) + list(schemas.values())
    seen: set[str] = set()
    for binding in bindings:
        if not isinstance(binding, dict):
            raise ValueError("each manifest artifact binding must be an object")
        relative = binding.get("path")
        digest = binding.get("sha256")
        parsed = relative_repository_path(relative, field="manifest artifact path")
        if not isinstance(digest, str) or HEX_64.fullmatch(digest) is None:
            raise ValueError("manifest artifact sha256 must be lowercase 64-hex")
        if relative in seen:
            raise ValueError(f"manifest repeats artifact path: {relative}")
        seen.add(relative)

        artifact = repository / parsed
        if artifact.is_symlink() or not artifact.is_file():
            raise ValueError(f"manifest-bound artifact is absent or a symlink: {relative}")
        observed = sha256(artifact)
        if observed != digest:
            raise ValueError(
                f"manifest-bound artifact digest mismatch for {relative}: "
                f"observed {observed}, declared {digest}"
            )
    return len(bindings)


def verify(lock_path: Path, repository: Path) -> list[str]:
    lock = validate_lock(json.loads(lock_path.read_bytes()))
    observed_commit = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if observed_commit != lock["commit"]:
        raise ValueError(
            f"corpus commit mismatch: observed {observed_commit}, locked {lock['commit']}"
        )

    entries = lock["vector_sets"]

    results = [f"corpus commit verified: {observed_commit}"]
    for entry in entries:
        candidate_id = entry["candidate_id"]
        candidate = repository / "vectors" / candidate_id
        if not candidate.is_dir():
            raise ValueError(f"locked candidate is absent: {candidate}")
        manifest = repository / entry["manifest_path"]
        if manifest.is_symlink() or not manifest.is_file():
            raise ValueError(f"locked manifest is absent: {manifest}")
        manifest_raw = manifest.read_bytes()
        observed_manifest = hashlib.sha256(manifest_raw).hexdigest()
        if observed_manifest != entry["manifest_sha256"]:
            raise ValueError(
                f"{candidate_id} manifest digest mismatch: observed "
                f"{observed_manifest}, locked {entry['manifest_sha256']}"
            )
        document = json.loads(manifest_raw)
        if not isinstance(document, dict):
            raise ValueError(f"{entry['manifest_path']} must contain a JSON object")
        if document.get("vector_set_id") != candidate_id:
            raise ValueError(
                f"{entry['manifest_path']} identifies {document.get('vector_set_id')!r}, "
                f"expected {candidate_id!r}"
            )
        if document.get("vector_set_sha256") != entry["vector_set_sha256"]:
            raise ValueError(
                f"{candidate_id} vector-set identity does not match the lock"
            )
        artifact_count = verify_manifest_artifacts(repository, document)
        results.append(
            f"{candidate_id}: manifest={observed_manifest} "
            f"vector_set={entry['vector_set_sha256']} artifacts={artifact_count}"
        )
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lock",
        type=Path,
        default=Path("config/wexp-vectors-core01.lock.json"),
    )
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        results = verify(args.lock, args.repository)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"CORPUS VERIFICATION FAIL — {exc}", file=sys.stderr)
        return 1
    for result in results:
        print(result)
    print("CORPUS VERIFICATION PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
