#!/usr/bin/env python3
"""Materialise a candidate directory from a seed.

Classification: **SHARED-INFRASTRUCTURE-SAFE**

This is the mechanism behind the zero-edit successor criterion: creating a
successor is running this tool against a seed file. It writes the descriptor,
the profile and the vectors, and computes every digest from the bytes it just
wrote, so no predecessor hash is ever transcribed by hand.

It deliberately does **not** derive expectations. Expected results are authored
in the seed by a human. Deriving them from an engine would make qualification
circular: the engines would be graded against their own output.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any, Sequence

if __package__ in {None, ""}:  # pragma: no cover - direct execution support
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wexp_ref.core01.harness import canonical
from wexp_ref.core01.harness.candidate import CandidateError, load


class SeedError(ValueError):
    """Raised when a seed cannot produce a well-formed candidate."""


def _vector_document(seed: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    profile = seed["profile"]
    document = {
        "vector_id": entry["vector_id"],
        "candidate_id": seed["candidate_id"],
        "snapshot": {
            "id": seed["authority"]["snapshot_id"],
            "xml_sha256": seed["authority"]["xml_sha256"],
        },
        "requirement_ids": entry["requirement_ids"],
        "source_fixture": entry["source_fixture"],
        "classification": entry["classification"],
        "purpose": entry["purpose"],
        "harness_representation": profile["harness"]["label"],
        "input": dict(entry["input"]),
        "expected_code": entry["expected_code"],
        "expected": entry["expected"],
    }
    document["input"].setdefault("representation", profile["representation"])
    document["input"].setdefault("semantics_version", profile["semantics_version"])
    if "derivation" in entry:
        document["derivation"] = entry["derivation"]
    return document


def build(seed_path: Path, output_root: Path, *, force: bool = False) -> Path:
    seed = canonical.load_json(seed_path)
    for key in ("candidate_id", "status", "authority", "profile", "vectors"):
        if key not in seed:
            raise SeedError(f"seed is missing {key!r}")

    root = output_root / seed["candidate_id"]
    if root.exists():
        if not force:
            raise SeedError(f"{root} already exists; refusing to overwrite without --force")
        shutil.rmtree(root)
    (root / "vectors").mkdir(parents=True)

    profile = dict(seed["profile"])
    profile.setdefault("profile_version", 1)
    bindings = {
        entry["vector_id"]: {
            "requirement_ids": entry["requirement_ids"],
            "source_fixture": entry["source_fixture"],
            "classification": entry["classification"],
        }
        for entry in seed["vectors"]
    }
    if len(bindings) != len(seed["vectors"]):
        raise SeedError("duplicate vector_id in seed")
    profile["vector_bindings"] = bindings

    profile_sha = canonical.write_canonical(root / "profile.json", profile)

    for entry in seed["vectors"]:
        document = _vector_document(seed, entry)
        canonical.write_canonical(root / "vectors" / f"{entry['vector_id']}.json", document)

    bound_files: list[dict[str, Any]] = []
    for path in sorted((root / "vectors").glob("*.json")):
        # One read: the digest and the size recorded here describe the same bytes.
        artifact = canonical.read_artifact(path)
        bound_files.append(
            {
                "kind": "test-vector",
                "path": f"vectors/{path.name}",
                "sha256": artifact.sha256,
                "bytes": artifact.size,
            }
        )

    descriptor = {
        "descriptor_version": 1,
        "candidate_id": seed["candidate_id"],
        "status": seed["status"],
        "authority": seed["authority"],
        "profile": {"path": "profile.json", "sha256": profile_sha},
        "bound_files": bound_files,
        "counts": {
            "vectors": len(bound_files),
            "requirements": len({r for e in seed["vectors"] for r in e["requirement_ids"]}),
        },
    }
    for optional in ("frozen_at_utc", "release_status", "immutability_rule", "non_claims"):
        if optional in seed:
            descriptor[optional] = seed[optional]

    canonical.write_canonical(root / "descriptor.json", descriptor)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("src/wexp_ref/core01/candidates"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        root = build(args.seed, args.output, force=args.force)
        candidate = load(root)
    except (SeedError, CandidateError, canonical.CanonicalError) as exc:
        print(f"CANDIDATE NOT CREATED — {exc}", file=sys.stderr)
        return 1

    identity = candidate.identity()
    print(f"candidate: {root}")
    for key in ("candidate_id", "descriptor_sha256", "profile_sha256", "vector_set_sha256"):
        print(f"  {key}: {identity[key]}")
    print(f"  vectors: {len(candidate.vectors)}")
    print("CANDIDATE CREATED AND VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
