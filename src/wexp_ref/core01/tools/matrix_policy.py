#!/usr/bin/env python3
"""Which environments a qualification run schedules, and what that run may claim.

Classification: **SHARED-INFRASTRUCTURE-SAFE**

The policy lives here rather than in a GitHub expression so that it is
reviewable and directly testable. The workflow asks this script what to run;
the script contains no candidate-specific logic and never names a candidate.

Policy:

* ``push`` schedules the portable leg only. It is developer feedback and is
  explicitly **not** sufficient evidence for qualification readiness.
* ``pull_request`` and ``workflow_dispatch`` schedule the full matrix:
  portable, Docker linux/amd64, native Darwin arm64, native Windows x64, and
  the cross-environment portability comparison.

The distinction this module also carries is between a *qualification result*
and *qualification execution availability*. A hosted runner refused for billing
or capacity reasons is neither a candidate failure nor a portability failure;
it is ``INFRASTRUCTURE EXECUTION UNAVAILABLE`` and is recorded as such.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Sequence

#: Every environment the full matrix observes, with the runner that hosts it.
FULL_MATRIX: tuple[dict[str, str], ...] = (
    {"environment": "portable", "runner": "ubuntu-latest"},
    {"environment": "docker", "runner": "ubuntu-latest"},
    {"environment": "darwin", "runner": "macos-15"},
    {"environment": "windows", "runner": "windows-latest"},
)

#: The fast developer-feedback subset.
PUSH_MATRIX: tuple[dict[str, str], ...] = (
    {"environment": "portable", "runner": "ubuntu-latest"},
)

#: Events that schedule the full matrix. Anything unrecognised is treated as a
#: full-matrix event: erring toward more observation is safe, erring toward less
#: would silently weaken the gate.
FULL_MATRIX_EVENTS = frozenset({"pull_request", "workflow_dispatch"})
REDUCED_EVENTS = frozenset({"push"})

#: Observation scopes, recorded in evidence so a reader cannot mistake one for
#: the other.
SCOPE_DEVELOPER_FEEDBACK = "developer-feedback"
SCOPE_FULL_MATRIX = "full-matrix"

#: Terminal vocabulary distinguishing a result from an execution problem.
INFRASTRUCTURE_UNAVAILABLE = "INFRASTRUCTURE EXECUTION UNAVAILABLE"


def plan(event_name: str) -> dict[str, Any]:
    """Return the matrix and the claim scope for an event."""

    reduced = event_name in REDUCED_EVENTS
    include = list(PUSH_MATRIX if reduced else FULL_MATRIX)
    return {
        "event": event_name,
        "include": include,
        "environments": [entry["environment"] for entry in include],
        "full_matrix": not reduced,
        "run_portability_comparison": not reduced,
        "observation_scope": SCOPE_DEVELOPER_FEEDBACK if reduced else SCOPE_FULL_MATRIX,
        "sufficient_for_qualification_readiness": not reduced,
        "note": (
            "A portable-only result is developer feedback. It does not satisfy the "
            "full-matrix requirement for qualification readiness."
            if reduced
            else "Full matrix: portable, Docker linux/amd64, native Darwin arm64 and "
            "native Windows x64, then the cross-environment portability comparison."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True, help="the GitHub event name")
    parser.add_argument(
        "--field",
        default=None,
        help="print a single field instead of the whole plan (e.g. include, full_matrix)",
    )
    args = parser.parse_args(argv)

    result = plan(args.event)
    if args.field:
        if args.field not in result:
            print(f"unknown field: {args.field}", file=sys.stderr)
            return 1
        value = result[args.field]
        print(json.dumps(value) if not isinstance(value, str) else value)
        return 0
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
