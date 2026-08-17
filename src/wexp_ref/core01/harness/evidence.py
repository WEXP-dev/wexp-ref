"""The generic evidence bundle.

Classification: **SHARED-INFRASTRUCTURE-SAFE**

Evidence is an envelope, not a judgement. This module records what each engine
observed, what the comparator concluded, and the exact identity everything was
computed against. It does not decide agreement; the comparator does.

The envelope deliberately differs from the frozen Candidate-001 artifacts: it
binds the profile digest and the environment, which the historical envelope had
no concept of. Migration therefore compares *semantic payloads*, not envelope
bytes, and says so explicitly rather than calling it bit-for-bit reproduction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import canonical
from .candidate import Candidate

EVIDENCE_VERSION = 1


@dataclass
class EngineObservation:
    engine_id: str
    implementation: str
    results: list[dict[str, Any]] = field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        """The semantic payload, free of envelope metadata.

        Migration equivalence is proven against this, because it contains the
        observations and nothing about where or when they were produced.
        """

        return {
            "engine_id": self.engine_id,
            "results": sorted(self.results, key=lambda item: item["vector_id"]),
        }

    def payload_sha256(self) -> str:
        return canonical.canonical_sha256(self.payload())


def build_bundle(
    candidate: Candidate,
    observations: list[EngineObservation],
    comparison: dict[str, Any],
    *,
    environment: dict[str, Any],
) -> dict[str, Any]:
    return {
        "evidence_version": EVIDENCE_VERSION,
        "record_kind": "wexp-generic-qualification-evidence",
        "candidate_identity": candidate.identity(),
        "environment": environment,
        "engines": [
            {
                "engine_id": observation.engine_id,
                "implementation": observation.implementation,
                "payload_sha256": observation.payload_sha256(),
                "results": observation.payload()["results"],
            }
            for observation in sorted(observations, key=lambda item: item.engine_id)
        ],
        "comparison": comparison,
        "non_claims": [
            "A qualification result is not a Publication Candidate, a freeze, or a ceremony.",
            "Agreement between engines is evidence of consistency, not of specification correctness.",
            "Environment observations describe this pipeline only; they are not historical "
            "observations of any previously frozen candidate.",
            "Values under environment.environment_specific are expected to differ between "
            "environments; values under environment.portable_claim are not.",
        ],
    }


def write_bundle(directory: Path, bundle: dict[str, Any]) -> dict[str, str]:
    """Write the bundle plus a per-engine payload file, returning digests."""

    directory.mkdir(parents=True, exist_ok=True)
    digests: dict[str, str] = {}
    for engine in bundle["engines"]:
        payload = {"engine_id": engine["engine_id"], "results": engine["results"]}
        digests[engine["engine_id"]] = canonical.write_canonical(
            directory / f"{engine['engine_id']}-payload.json", payload
        )
    digests["comparison"] = canonical.write_canonical(
        directory / "comparison.json", bundle["comparison"]
    )
    digests["bundle"] = canonical.write_canonical(directory / "QUALIFICATION.json", bundle)
    return digests
