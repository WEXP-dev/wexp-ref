"""Show one vector's input, expected result and observed result.

Classification: **SHARED-INFRASTRUCTURE-SAFE**

The orchestrator evaluates a whole candidate, which is right for qualification
but wrong for understanding: someone asking "why did C06 come out that way?"
should not have to read an evidence bundle by hand. This runs the same engines
through the same harness and prints one vector.

It makes no semantic decision of its own and cannot change a verdict. Expected
results come from the vector, never from an engine.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from wexp_ref.core01.harness.candidate import load
from wexp_ref.core01.harness.engine import load_engine


def _select(candidate, wanted: str):
    for vector in candidate.vectors:
        if wanted in (vector.vector_id, vector.payload.get("source_fixture")):
            return vector
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--vector", required=True, help="vector id or source fixture, e.g. C06")
    parser.add_argument("--json", dest="json_out", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    candidate = load(args.candidate)
    vector = _select(candidate, args.vector)
    if vector is None:
        available = ", ".join(
            f"{v.payload.get('source_fixture')}={v.vector_id}" for v in candidate.vectors
        )
        print(f"no such vector: {args.vector!r}\navailable: {available}", file=sys.stderr)
        return 1

    observed = {name: load_engine(name).evaluate(vector, candidate) for name in ("independent", "reference")}
    agree = json.dumps(observed["independent"], sort_keys=True) == json.dumps(
        observed["reference"], sort_keys=True
    )
    expected = vector.payload["expected"]
    met = all(json.dumps(o, sort_keys=True) == json.dumps(expected, sort_keys=True) for o in observed.values())

    if args.json_out:
        print(json.dumps({
            "vector_id": vector.vector_id,
            "source_fixture": vector.payload.get("source_fixture"),
            "classification": vector.payload.get("classification"),
            "expected_code": vector.payload.get("expected_code"),
            "input": vector.payload["input"],
            "expected": expected,
            "observed": observed,
            "engines_agree": agree,
            "expectation_met": met,
        }, indent=2, sort_keys=True))
        return 0 if met and agree else 1

    print(f"vector      {vector.vector_id}")
    print(f"fixture     {vector.payload.get('source_fixture')}")
    print(f"class       {vector.payload.get('classification')}")
    print(f"expects     {vector.payload.get('expected_code') or '(no reason token)'}")
    print(f"purpose     {vector.payload.get('purpose')}")
    print(f"derivation  {vector.payload.get('derivation')}")
    print()
    print(f"asserted claim   {json.dumps(vector.payload['input']['asserted_claim'])}")
    print(f"boundary ceiling {vector.payload['input']['boundary_finding']['ceiling_base']}")
    print()
    ind = observed["independent"]
    print(f"verdict          {ind.get('verdict')}")
    print(f"claim supported  {ind.get('asserted_claim_supported')}")
    print(f"ceiling          {ind.get('boundary_ceiling')}  grounding {ind.get('boundary_grounding')}")
    print(f"substantive      {ind.get('substantive_reasons')}")
    print(f"fatal            {ind.get('fatal_reasons')}")
    print(f"gaps             {ind.get('evaluation_gaps')}")
    print()
    print(f"engines agree    {agree}")
    print(f"matches expected {met}")
    return 0 if met and agree else 1


if __name__ == "__main__":
    raise SystemExit(main())
