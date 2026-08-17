#!/usr/bin/env python3
"""Compare qualification bundles produced in different environments.

Classification: **SHARED-INFRASTRUCTURE-SAFE**

This is what makes "portable" a checked claim rather than an assertion. Given
the bundles from two or more environments it separates:

* **portable** fields, which must be identical everywhere — the candidate
  identity, each engine's payload digest, and the comparison summary. Any
  difference here is a portability failure and is reported as such.
* **environment-specific** fields, which are expected to differ and are
  enumerated so a reader can see exactly what varied and where.

It never edits a bundle and never decides a verdict.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

if __package__ in {None, ""}:  # pragma: no cover - direct execution support
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wexp_ref.core01.harness import canonical

PORTABLE = "PORTABLE ACROSS ENVIRONMENTS"
NOT_PORTABLE = "NOT PORTABLE"
INCOMPLETE = "FULL-MATRIX OBSERVATION INCOMPLETE"

#: The environments a formal full-matrix observation must include. Comparing a
#: subset is legitimate engineering evidence but must never be reported as the
#: full-matrix observation that qualification readiness requires.
REQUIRED_FULL_MATRIX = frozenset({"portable", "docker", "darwin"})


def portable_projection(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_identity": bundle["candidate_identity"],
        "engine_payloads": {
            engine["engine_id"]: engine["payload_sha256"] for engine in bundle["engines"]
        },
        "comparison_summary": bundle["comparison"]["summary"],
        "comparison_status": bundle["comparison"]["status"],
    }


def compare(bundles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if len(bundles) < 2:
        raise ValueError("at least two environment bundles are required")

    missing = sorted(REQUIRED_FULL_MATRIX - set(bundles))
    full_matrix = not missing

    projections = {label: portable_projection(bundle) for label, bundle in bundles.items()}
    digests = {label: canonical.canonical_sha256(value) for label, value in projections.items()}
    unique = sorted(set(digests.values()))

    differing_fields: list[str] = []
    if len(unique) != 1:
        reference_label = sorted(projections)[0]
        reference = projections[reference_label]
        for label, projection in projections.items():
            if label == reference_label:
                continue
            for key in sorted(reference):
                if projection[key] != reference[key]:
                    differing_fields.append(f"{key}: {reference_label} vs {label}")

    varied: dict[str, dict[str, Any]] = {}
    for label, bundle in sorted(bundles.items()):
        for name in bundle["environment"]["environment_specific"]:
            varied.setdefault(name, {})[label] = bundle["environment"]["observations"].get(name)
    genuinely_varied = {
        name: values for name, values in varied.items() if len(set(map(repr, values.values()))) > 1
    }

    return {
        "record_kind": "wexp-environment-portability-comparison",
        "environments": sorted(bundles),
        "full_matrix_observation": full_matrix,
        "missing_required_environments": missing,
        "observation_scope": "full-matrix" if full_matrix else "partial",
        "sufficient_for_qualification_readiness": full_matrix and len(unique) == 1,
        "portable_projection_sha256": digests,
        "portable": len(unique) == 1,
        "portable_differences": sorted(set(differing_fields)),
        "environment_specific_observations": varied,
        "observations_that_actually_varied": genuinely_varied,
        "non_claims": [
            "Portability here means the engines produced the same semantic payload; "
            "it is not a claim about any environment's correctness.",
            "These are observations of this migration pipeline, not of any previously "
            "frozen candidate.",
            "A partial comparison is supporting evidence only. It does not satisfy the "
            "full-matrix requirement for qualification readiness.",
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        action="append",
        required=True,
        metavar="LABEL=PATH",
        help="repeatable; e.g. --bundle portable=build/portable/X/QUALIFICATION.json",
    )
    parser.add_argument("--json", dest="json_out", type=Path, default=None)
    parser.add_argument(
        "--require-full-matrix",
        action="store_true",
        help="fail unless every required environment is present; use for the formal gate",
    )
    args = parser.parse_args(argv)

    bundles: dict[str, dict[str, Any]] = {}
    for item in args.bundle:
        label, _, raw = item.partition("=")
        if not raw:
            print(f"NOT PORTABLE — malformed --bundle {item!r}", file=sys.stderr)
            return 1
        bundles[label] = canonical.load_json(Path(raw))

    try:
        report = compare(bundles)
    except (ValueError, canonical.CanonicalError) as exc:
        print(f"{NOT_PORTABLE} — {exc}", file=sys.stderr)
        return 1

    for label in report["environments"]:
        print(f"{label}: portable_projection_sha256={report['portable_projection_sha256'][label]}")
    for name, values in sorted(report["observations_that_actually_varied"].items()):
        print(f"varied: {name}: {values}")
    if args.json_out:
        canonical.write_canonical(args.json_out, report)
    if args.require_full_matrix and not report["full_matrix_observation"]:
        print(
            f"{INCOMPLETE} — missing: {', '.join(report['missing_required_environments'])}",
            file=sys.stderr,
        )
        return 1
    if not report["portable"]:
        for difference in report["portable_differences"]:
            print(f"DIFFERENCE: {difference}", file=sys.stderr)
        print(NOT_PORTABLE, file=sys.stderr)
        return 1
    scope = report["observation_scope"]
    print(f"{PORTABLE} (observation scope: {scope})")
    if not report["full_matrix_observation"]:
        print(
            "supporting evidence only; missing "
            f"{', '.join(report['missing_required_environments'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
