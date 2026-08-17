"""Generic candidate loading, verification and identity binding.

Classification: **SHARED-INFRASTRUCTURE-SAFE**

This module answers "what is this candidate, and are its bytes the ones it
claims?". It never decides a verdict, never interprets a reason token, and
never ranks a claim. Those are the engines' work and are deliberately kept out
of any shared module, because a shared fault there would defeat the differential
comparison.

Trust model for profile data, enforced here:

* schema validated before any engine sees it;
* digest-bound to the descriptor, which is itself the candidate's identity;
* canonicalised for digesting, so formatting cannot change identity;
* versioned, and an unknown version is rejected rather than assumed compatible;
* cross-checked against the vectors, so a binding stated in the profile and a
  binding stated in a vector must agree;
* fail-closed: anything missing, duplicated, unresolvable or ambiguous raises.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from . import canonical, schema as schema_module

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schema"
SUPPORTED_DESCRIPTOR_VERSIONS = frozenset({1})
SUPPORTED_PROFILE_VERSIONS = frozenset({1})


class CandidateError(ValueError):
    """Raised when a candidate is incomplete, inconsistent or unverifiable."""


@dataclass(frozen=True)
class Vector:
    vector_id: str
    path: Path
    sha256: str
    payload: dict[str, Any]

    @property
    def input(self) -> dict[str, Any]:
        return self.payload["input"]

    @property
    def expected(self) -> dict[str, Any]:
        return self.payload["expected"]

    @property
    def expected_code(self) -> str:
        return self.payload["expected_code"]


@dataclass(frozen=True)
class Candidate:
    root: Path
    descriptor: dict[str, Any]
    descriptor_sha256: str
    profile: dict[str, Any]
    profile_sha256: str
    vectors: tuple[Vector, ...]

    @property
    def candidate_id(self) -> str:
        return self.descriptor["candidate_id"]

    @property
    def snapshot_id(self) -> str:
        return self.descriptor["authority"]["snapshot_id"]

    @property
    def snapshot_sha256(self) -> str:
        return self.descriptor["authority"]["xml_sha256"]

    @property
    def semantics_version(self) -> str:
        return self.profile["semantics_version"]

    @property
    def representation(self) -> str:
        return self.profile["representation"]

    def identity(self) -> dict[str, str]:
        """The identity every evidence bundle binds itself to.

        The profile digest is part of the identity: a candidate whose semantic
        data changed is a different candidate, even if its vectors did not.
        """

        return {
            "candidate_id": self.candidate_id,
            "descriptor_sha256": self.descriptor_sha256,
            "profile_id": self.profile["profile_id"],
            "profile_sha256": self.profile_sha256,
            "snapshot_id": self.snapshot_id,
            "snapshot_xml_sha256": self.snapshot_sha256,
            "semantics_version": self.semantics_version,
            "vector_set_sha256": canonical.canonical_sha256(
                [[vector.vector_id, vector.sha256] for vector in self.vectors]
            ),
        }

    def __iter__(self) -> Iterator[Vector]:
        return iter(self.vectors)


def _load_schema(name: str) -> dict[str, Any]:
    document = canonical.load_json(SCHEMA_DIR / f"{name}.schema.json")
    if not isinstance(document, dict):
        raise CandidateError(f"{name}.schema.json: schema must be an object")
    return document


def _validate(instance: Any, name: str, location: str) -> None:
    try:
        schema_module.validate(instance, _load_schema(name), location=location)
    except (schema_module.ValidationError, schema_module.SchemaError) as exc:
        raise CandidateError(f"{location}: {exc}") from exc


def _resolve_inside(root: Path, relative: str, *, what: str) -> Path:
    if relative.startswith("/") or "\\" in relative:
        raise CandidateError(f"{what}: path must be relative POSIX: {relative!r}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise CandidateError(f"{what}: path escapes the candidate: {relative!r}") from exc
    if candidate.is_symlink():
        raise CandidateError(f"{what}: symlinks are not accepted: {relative!r}")
    return candidate


def _verify_bound_files(root: Path, descriptor: dict[str, Any]) -> None:
    seen: set[str] = set()
    for entry in descriptor["bound_files"]:
        relative = entry["path"]
        if relative in seen:
            raise CandidateError(f"bound_files: duplicate path {relative!r}")
        seen.add(relative)
        path = _resolve_inside(root, relative, what="bound_files")
        if not path.is_file():
            raise CandidateError(f"bound_files: missing file {relative!r}")
        actual = canonical.file_sha256(path)
        if actual != entry["sha256"]:
            raise CandidateError(
                f"bound_files: SHA-256 mismatch for {relative!r}: declared {entry['sha256']}, observed {actual}"
            )
        size = canonical.file_bytes(path)
        if size != entry["bytes"]:
            raise CandidateError(
                f"bound_files: size mismatch for {relative!r}: declared {entry['bytes']}, observed {size}"
            )


def _cross_check_vector(vector: Vector, candidate_id: str, profile: dict[str, Any]) -> None:
    payload = vector.payload
    if payload["candidate_id"] != candidate_id:
        raise CandidateError(
            f"{vector.vector_id}: declares candidate {payload['candidate_id']!r}, expected {candidate_id!r}"
        )
    if payload["harness_representation"] != profile["harness"]["label"]:
        raise CandidateError(
            f"{vector.vector_id}: harness representation does not match the profile harness label"
        )

    binding = profile["vector_bindings"].get(vector.vector_id)
    if binding is None:
        raise CandidateError(f"{vector.vector_id}: no binding in the profile")
    for field in ("requirement_ids", "source_fixture", "classification"):
        if payload[field] != binding[field]:
            raise CandidateError(
                f"{vector.vector_id}: {field} disagrees between the vector and the profile binding"
            )

    semantics = payload["input"].get("semantics_version")
    if semantics is not None and semantics != profile["semantics_version"]:
        raise CandidateError(
            f"{vector.vector_id}: input semantics_version {semantics!r} != profile {profile['semantics_version']!r}"
        )
    representation = payload["input"].get("representation")
    if representation is not None and representation != profile["representation"]:
        raise CandidateError(
            f"{vector.vector_id}: input representation {representation!r} != profile representation"
        )


def known_tokens(profile: dict[str, Any]) -> frozenset[str]:
    """Every token this candidate may legitimately emit."""

    classes = profile["token_registry"]["classes"]
    return frozenset(token for group in classes.values() for token in group)


def token_for(profile: dict[str, Any], role: str) -> str:
    """The token name this candidate uses for a fixed engine role."""

    roles = profile["token_registry"]["roles"]
    if role not in roles:
        raise CandidateError(f"profile declares no token for role {role!r}")
    return roles[role]


def load(root: Path) -> Candidate:
    """Load and fully verify a candidate directory. Fail closed on anything odd."""

    root = root.resolve()
    if not root.is_dir():
        raise CandidateError(f"candidate directory does not exist: {root}")

    descriptor_path = root / "descriptor.json"
    descriptor = canonical.load_json(descriptor_path)
    _validate(descriptor, "descriptor", "descriptor.json")
    if descriptor["descriptor_version"] not in SUPPORTED_DESCRIPTOR_VERSIONS:
        raise CandidateError(f"unsupported descriptor_version: {descriptor['descriptor_version']}")
    if root.name != descriptor["candidate_id"]:
        raise CandidateError(
            f"directory name {root.name!r} must equal candidate_id {descriptor['candidate_id']!r}"
        )

    profile_path = _resolve_inside(root, descriptor["profile"]["path"], what="profile")
    profile_digest = canonical.file_sha256(profile_path)
    if profile_digest != descriptor["profile"]["sha256"]:
        raise CandidateError(
            f"profile digest mismatch: declared {descriptor['profile']['sha256']}, observed {profile_digest}"
        )
    profile = canonical.load_json(profile_path)
    _validate(profile, "profile", "profile.json")
    if profile["profile_version"] not in SUPPORTED_PROFILE_VERSIONS:
        raise CandidateError(f"unsupported profile_version: {profile['profile_version']}")

    _verify_bound_files(root, descriptor)

    vector_schema = _load_schema("vector")
    vectors: list[Vector] = []
    vector_dir = root / "vectors"
    if not vector_dir.is_dir():
        raise CandidateError("candidate has no vectors/ directory")
    for path in sorted(vector_dir.glob("*.json")):
        payload = canonical.load_json(path)
        try:
            schema_module.validate(payload, vector_schema, location=path.name)
        except (schema_module.ValidationError, schema_module.SchemaError) as exc:
            raise CandidateError(f"{path.name}: {exc}") from exc
        vector = Vector(
            vector_id=payload["vector_id"],
            path=path,
            sha256=canonical.file_sha256(path),
            payload=payload,
        )
        if path.stem != vector.vector_id:
            raise CandidateError(f"{path.name}: filename must equal vector_id {vector.vector_id!r}")
        _cross_check_vector(vector, descriptor["candidate_id"], profile)
        vectors.append(vector)

    if not vectors:
        raise CandidateError("candidate declares no vectors")
    declared = set(profile["vector_bindings"])
    present = {vector.vector_id for vector in vectors}
    if declared != present:
        missing = sorted(declared - present)
        extra = sorted(present - declared)
        detail = []
        if missing:
            detail.append("bound but absent: " + ", ".join(missing))
        if extra:
            detail.append("present but unbound: " + ", ".join(extra))
        raise CandidateError("vector set disagrees with the profile bindings; " + "; ".join(detail))

    expected_count = descriptor["counts"].get("vectors")
    if expected_count is not None and expected_count != len(vectors):
        raise CandidateError(
            f"counts.vectors declares {expected_count} but {len(vectors)} vector(s) are present"
        )

    return Candidate(
        root=root,
        descriptor=descriptor,
        descriptor_sha256=canonical.file_sha256(descriptor_path),
        profile=profile,
        profile_sha256=profile_digest,
        vectors=tuple(vectors),
    )
