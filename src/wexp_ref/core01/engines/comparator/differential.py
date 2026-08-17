"""Differential comparator.

Classification: **ASSURANCE-CRITICAL — MUST REMAIN INDEPENDENT**

The comparator is the third distinct assurance role. It decides three things
that neither engine may decide about itself:

1. whether the engines agree with each other;
2. whether each engine agrees with the candidate's frozen expectation;
3. whether the required coverage was actually exercised.

It reads the ``expected`` payload; the engines never do. It imports no engine,
so a fault inside one engine cannot propagate into the judgement about that
engine.
"""

from __future__ import annotations

from typing import Any, Sequence

from wexp_ref.core01.harness import canonical
from wexp_ref.core01.harness.candidate import Candidate

AGREE = "AGREE"
DISAGREE = "DISAGREE"


def _projection(actual: dict[str, Any]) -> dict[str, Any]:
    """The comparable projection of an engine result.

    Engines may record diagnostic detail; only the semantic projection is
    compared, and it is compared canonically so key order cannot cause a false
    disagreement.
    """

    return {key: actual[key] for key in sorted(actual) if not key.startswith("diagnostic_")}


def compare(candidate: Candidate, observations: Sequence[Any]) -> dict[str, Any]:
    if len(observations) < 2:
        return {
            "status": "FAIL",
            "reason": "differential comparison requires at least two independent engines",
            "summary": {"vectors": 0, "agree": 0, "disagree": 0, "expected_mismatch": 0},
            "vectors": [],
        }

    by_engine: dict[str, dict[str, dict[str, Any]]] = {}
    for observation in observations:
        by_engine[observation.engine_id] = {
            item["vector_id"]: item for item in observation.results
        }

    engine_ids = sorted(by_engine)
    rows: list[dict[str, Any]] = []
    agree = disagree = mismatched = 0

    for vector in candidate:
        expected = vector.expected
        expected_digest = canonical.canonical_sha256(_projection(expected))
        per_engine: dict[str, Any] = {}
        projections: list[str] = []
        engine_faulted = False

        for engine_id in engine_ids:
            item = by_engine[engine_id].get(vector.vector_id)
            if item is None:
                per_engine[engine_id] = {"present": False}
                projections.append(f"absent:{engine_id}")
                engine_faulted = True
                continue
            actual = item["actual"]
            if "engine_error" in actual:
                engine_faulted = True
            digest = canonical.canonical_sha256(_projection(actual))
            projections.append(digest)
            per_engine[engine_id] = {
                "present": True,
                "projection_sha256": digest,
                "matches_expected": digest == expected_digest,
                "engine_error": actual.get("engine_error"),
            }

        engines_agree = len(set(projections)) == 1 and not engine_faulted
        expectation_met = all(
            entry.get("matches_expected") is True for entry in per_engine.values()
        )
        agree += 1 if engines_agree else 0
        disagree += 0 if engines_agree else 1
        mismatched += 0 if expectation_met else 1

        rows.append(
            {
                "vector_id": vector.vector_id,
                "source_fixture": vector.payload["source_fixture"],
                "classification": vector.payload["classification"],
                "requirement_ids": vector.payload["requirement_ids"],
                "expected_code": vector.expected_code,
                "expected_sha256": expected_digest,
                "engines": per_engine,
                "engines_agree": AGREE if engines_agree else DISAGREE,
                "expectation_met": expectation_met,
            }
        )

    bound_requirements = {
        requirement
        for binding in candidate.profile["vector_bindings"].values()
        for requirement in binding["requirement_ids"]
    }
    exercised = {
        requirement for row in rows for requirement in row["requirement_ids"]
    }
    uncovered = sorted(bound_requirements - exercised)

    status = "PASS" if not disagree and not mismatched and not uncovered else "FAIL"
    return {
        "status": status,
        "engines": engine_ids,
        "summary": {
            "vectors": len(rows),
            "agree": agree,
            "disagree": disagree,
            "expected_mismatch": mismatched,
            "uncovered_requirements": len(uncovered),
        },
        "uncovered_requirements": uncovered,
        "vectors": rows,
    }
