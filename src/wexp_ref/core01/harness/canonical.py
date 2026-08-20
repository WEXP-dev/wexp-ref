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
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Artifact:
    """One filesystem read, and everything derived from that single buffer.

    Digest, size and parsed value all describe the same bytes because there is
    only ever one read. Hashing a file and then parsing it in a second,
    independent read cannot be proven to describe the same content: anything that
    rewrites the path between the two makes the recorded digest attest to bytes
    that were never evaluated. Evidence identity must not depend on the filesystem
    holding still, so no artifact that contributes to one is read twice.
    """

    path: Path
    raw: bytes
    sha256: str

    @property
    def size(self) -> int:
        return len(self.raw)

    def json(self) -> Any:
        """Parse the buffer this digest was computed over. No second read."""
        return loads_bytes(self.raw, origin=str(self.path))


def is_line_ending_only_mismatch(artifact: Artifact, declared_sha256: str) -> bool:
    """Detect a likely LF/CRLF checkout rewrite without accepting changed bytes.

    This is diagnostic only. It derives alternate newline forms from the buffer
    that was already read and digested, preserving the single-read invariant.
    Binary-looking content is deliberately excluded: the bytes must be strict
    UTF-8 and contain no NUL byte. A match here never makes the observed bytes
    equivalent to the declared bytes and must not change a failure verdict.
    """

    raw = artifact.raw
    if artifact.sha256 == declared_sha256 or b"\x00" in raw:
        return False
    try:
        raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return False

    lf = raw.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    return any(
        variant != raw and hashlib.sha256(variant).hexdigest() == declared_sha256
        for variant in (lf, crlf)
    )


def read_artifact(path: Path) -> Artifact:
    """Read a path exactly once and bind its bytes, digest and size together."""

    if path.is_symlink():
        raise CanonicalError(f"symlinks are not accepted: {path}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CanonicalError(f"{path}: unreadable: {exc}") from exc
    return Artifact(path=path, raw=raw, sha256=hashlib.sha256(raw).hexdigest())


def loads_bytes(raw: bytes, *, origin: str = "<bytes>") -> Any:
    """Parse a UTF-8 JSON buffer under the same rules as ``loads``."""

    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise CanonicalError(f"{origin}: not valid UTF-8: {exc}") from exc
    return loads(text, origin=origin)


def load_json(path: Path) -> Any:
    """Read JSON strictly: no duplicate keys, no NaN/Infinity, UTF-8 only.

    For anything whose digest is recorded, use ``read_artifact`` instead so the
    digest and the parse cannot disagree.
    """

    return read_artifact(path).json()


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


# ``file_sha256`` and ``file_bytes`` were removed rather than kept alongside
# ``read_artifact``. Both digested or measured a path independently of whoever
# parsed it, so any caller pairing one with a load reintroduced the two-read
# defect. Deleting them makes the single-read invariant structural instead of a
# convention a future caller has to remember.


def write_canonical(path: Path, value: Any) -> str:
    """Write a value in canonical form and return its digest."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_bytes(value)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()
