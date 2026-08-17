"""Generic qualification orchestration.

Classification: **SHARED-INFRASTRUCTURE-SAFE**

Loads a candidate, runs each engine over every vector, hands the observations to
the comparator, and writes the evidence bundle. It contains no semantic
decision: it does not know what a verdict means, and it does not compare
results itself.

The orchestrator never shows an engine the expected payload. Engines receive the
vector and the candidate; the expectation is applied afterwards, by the
comparator, so an engine cannot accidentally be graded against a value it has
already seen.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

if __package__ in {None, ""}:  # pragma: no cover - direct execution support
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wexp_ref.core01.harness import (
    canonical,
    environment as environment_module,
    evidence as evidence_module,
)
from wexp_ref.core01.harness.candidate import Candidate, CandidateError, load
from wexp_ref.core01.harness.engine import ENGINE_MODULES, load_engine

QUALIFIED = "QUALIFICATION PASS"
NOT_QUALIFIED = "QUALIFICATION FAIL"


class OrchestrationError(RuntimeError):
    """Raised when qualification cannot be carried out as specified."""


@dataclass(frozen=True)
class Outcome:
    status: str
    bundle: dict[str, Any]
    digests: dict[str, str]

    @property
    def ok(self) -> bool:
        return self.status == QUALIFIED


def run_engine(name: str, candidate: Candidate) -> evidence_module.EngineObservation:
    engine = load_engine(name)
    observation = evidence_module.EngineObservation(
        engine_id=engine.engine_id, implementation=engine.implementation
    )
    for vector in candidate:
        try:
            actual = engine.evaluate(vector, candidate)
        except Exception as exc:  # noqa: BLE001 - an engine fault is evidence, not a crash
            actual = {
                "engine_error": type(exc).__name__,
                "detail": str(exc),
                "traceback": traceback.format_exc(limit=3),
            }
        observation.results.append(
            {
                "vector_id": vector.vector_id,
                "vector_sha256": vector.sha256,
                "actual": actual,
                "actual_sha256": canonical.canonical_sha256(actual),
            }
        )
    return observation


def compare(candidate: Candidate, observations: Sequence[evidence_module.EngineObservation]) -> dict[str, Any]:
    """Delegate to the differential comparator, which is assurance-critical."""

    from wexp_ref.core01.engines.comparator import differential

    return differential.compare(candidate, observations)


def qualify(
    candidate_root: Path,
    output_root: Path,
    *,
    environment_label: str,
    engines: Sequence[str] = tuple(ENGINE_MODULES),
) -> Outcome:
    environment = environment_module.observe(
        environment_module.load_descriptor(environment_label)
    )
    candidate = load(candidate_root)
    observations = [run_engine(name, candidate) for name in engines]
    comparison = compare(candidate, observations)
    bundle = evidence_module.build_bundle(
        candidate, observations, comparison, environment=environment
    )
    digests = evidence_module.write_bundle(output_root / candidate.candidate_id, bundle)
    status = QUALIFIED if comparison["status"] == "PASS" else NOT_QUALIFIED
    return Outcome(status=status, bundle=bundle, digests=digests)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("build/qualification"))
    parser.add_argument("--environment", default="portable")
    parser.add_argument("--engine", action="append", dest="engines", default=None)
    args = parser.parse_args(argv)

    try:
        outcome = qualify(
            args.candidate,
            args.output,
            environment_label=args.environment,
            engines=tuple(args.engines) if args.engines else tuple(ENGINE_MODULES),
        )
    except (
        CandidateError,
        OrchestrationError,
        canonical.CanonicalError,
        environment_module.EnvironmentError_,
    ) as exc:
        print(f"{NOT_QUALIFIED} — {exc}", file=sys.stderr)
        return 1

    identity = outcome.bundle["candidate_identity"]
    print(f"candidate: {identity['candidate_id']}")
    print(f"profile:   {identity['profile_id']} sha256={identity['profile_sha256']}")
    print(f"vectors:   {identity['vector_set_sha256']}")
    for engine in outcome.bundle["engines"]:
        print(f"engine:    {engine['engine_id']} payload_sha256={engine['payload_sha256']}")
    env = outcome.bundle["environment"]
    print(f"environment: {env['label']} ({env['kind']}) "
          f"{env['observations']['system']}/{env['observations']['machine']}")
    summary = outcome.bundle["comparison"]["summary"]
    print(f"comparison: {summary}")
    print(f"bundle:    {outcome.digests['bundle']}")
    print(outcome.status)
    return 0 if outcome.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
