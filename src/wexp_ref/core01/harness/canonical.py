"""Canonical serialisation and digests.

Classification: **SHARED-INFRASTRUCTURE-SAFE**

Both semantic engines may use this module. A fault here produces a wrong digest
or a read failure, which is loud and symmetric: it cannot cause the independent
evaluator and the reference implementation to agree on a wrong *verdict*, which
is the property the differential comparison exists to detect. Nothing in this
module interprets WEXP semantics.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class CanonicalError(ValueError):
    """Raised when input cannot be read or canonicalised unambiguously."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CanonicalError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise CanonicalError(f"non-standard JSON constant: {value}")


def load_json(path: Path) -> Any:
    """Read JSON strictly: no duplicate keys, no NaN/Infinity, UTF-8 only."""

    if path.is_symlink():
        raise CanonicalError(f"symlinks are not accepted: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CanonicalError(f"{path}: unreadable: {exc}") from exc
    return loads(text, origin=str(path))


def loads(text: str, *, origin: str = "<string>") -> Any:
    try:
        return json.loads(
            text, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant
        )
    except json.JSONDecodeError as exc:
        raise CanonicalError(f"{origin}: invalid JSON: {exc}") from exc


def canonical_bytes(value: Any) -> bytes:
    """Deterministic JSON encoding used for every digest this pipeline records.

    Sorted keys, no insignificant whitespace, UTF-8, and a trailing newline so
    the encoding is a well-formed text file as well as a byte string.
    """

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    ) + b"\n"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise CanonicalError(f"{path}: unreadable: {exc}") from exc
    return digest.hexdigest()


def file_bytes(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError as exc:
        raise CanonicalError(f"{path}: unreadable: {exc}") from exc


def write_canonical(path: Path, value: Any) -> str:
    """Write a value in canonical form and return its digest."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_bytes(value)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()
