# WEXP Reference Implementation

WEXP (Witnessed Execution Protocol) is an IETF-oriented specification effort
for evaluating support for claims about software and AI execution within
explicit evidence and observation boundaries.

This repository contains the WEXP reference implementation and related test
tools. The current Python 3.12+ package implements a small, revision-scoped
Core `-00` vector slice. It also checks XML parsing and the `wexp-vectors`
dependency lock and provides a generic execution runner.

> The WEXP specifications are authoritative. This implementation does not
> define WEXP.

The package is pre-alpha. Passing one of its checks does not prove protocol
correctness, interoperability, conformance by an independent implementation,
IETF acceptance, or the validity of an execution claim.

## Relationship to the specifications

The currently published WEXP specification is
[Core `-00`](https://datatracker.ietf.org/doc/html/draft-sergeev-wexp-core-00),
an Internet-Draft. The reference implementation may lag behind the specifications.
A missing feature here does not mean that it is absent from a specification.
This implementation cannot add, replace, or reinterpret specification
requirements. Pre-publication development is maintained separately.

## WEXP repositories

- [Specifications — `wexp-spec`](https://github.com/WEXP-dev/wexp-spec) —
  published WEXP specifications and their provenance.
- [Test vectors — `wexp-vectors`](https://github.com/WEXP-dev/wexp-vectors) —
  schemas and validation tools for implementation-independent WEXP test vectors.
- [Reference implementation — `wexp-ref`](https://github.com/WEXP-dev/wexp-ref)
  — the reference implementation and generic execution tools.

## Available

The CLI currently provides:

- `core00-run-vectors`: execute the specification-derived Core `-00` candidate
  vectors from the exact package named by the dependency lock;
- `validate-xml`: parse an XML file and report its SHA-256 digest;
- `validate-lock`: check the exact `wexp-vectors` dependency identity; and
- `run`: execute a declarative argv-only plan and record observations.

The Core `-00` commands consume an abstract test representation, not a WEXP
record or wire format. They implement only the rules exercised by the first
vector slice. A successful XML parse does not establish conformance with WEXP
or IETF acceptance. Lock validation checks dependency metadata only; the
separate package command performs the vector execution.

## Current limitations

- The package does not yet implement the full Core `-00` verification model.
  It does not parse or verify Core records, signatures, timestamps, key
  bindings, capabilities documents, recorder qualifications, or chains. The
  test harness supplies reviewed facts for these out-of-slice checks.
- No normative WEXP vector package has been released. The dependency lock pins
  an exact candidate package of specification-derived vectors; CI fetches and
  executes only that commit. The candidate is not designated normative or
  conformance-establishing.
- The runner is not a sandbox. Its observations are specific to this
  implementation, not standardized WEXP records or evidence of conformance.

## Local use

The package has no runtime dependencies:

```sh
python3 -m pip install --no-deps .
wexp-ref --version
wexp-ref validate-lock
wexp-ref validate-xml path/to/document.xml
wexp-ref core00-run-vectors path/to/exact/wexp-vectors \
  --output build/core00-results.json
python3 scripts/validate_repository.py
```

From a source checkout without installation, prefix commands with
`PYTHONPATH=src`.

## Generic runner

The runner consumes a declarative JSON plan. Plans declare inputs, argv-only
steps, outputs, source and dependency identities, claims, and non-claims.
Commands are passed directly to `subprocess.run(..., shell=False)`; `{python}`
and `{workspace}` are the only whole-argument substitutions. The runner hashes
declared inputs and observed output files and records timestamps, argv,
stdout/stderr hashes, observations, and exit statuses.

```sh
PYTHONPATH=src python3 -m wexp_ref run \
  examples/runner-smoke-plan.json \
  --workspace . \
  --record WEXP-REF-RUNNER-OBSERVATION.json
```

A plan can execute any declared program available to the caller. The runner
records declared files but cannot prove that a process touched no other
resource. Review plans before running them and use least privilege.

The example command emits records with
`record_kind: wexp-ref-runner-observation`. These records are specific to this
implementation. They are not standardized WEXP protocol records or evidence of
protocol conformance.

Every emitted record states that it does not establish IETF acceptance,
independent implementation conformance, complete WEXP correctness, or
standardized protocol-record status.

## Core -00 vector slice

The checked-in lock identifies `WEXP-dev/wexp-vectors` commit
`714a0ea4b269a5f8845adf727adfa6e6bba5bb03` and manifest SHA-256
`7cea69feae2f5aff309881e7228f5a7bf62ca3cdaa672d0de9d6324022cff306`.
The manifest identity and every manifest-bound file digest are checked before
execution. CI additionally confirms that the fetched Git checkout has exactly
the locked commit.

The evaluator is deliberately revision-scoped. It accepts only the frozen
Core `-00` harness facts used by the candidate vectors and rejects other
boundary types or input members. Expected results remain part of the vector
package; `wexp-ref` reports agreement or disagreement without rewriting them.
The result file is deterministic and machine-readable.

The candidate package contains seven specification-derived test vectors. It is
not a released normative vector package or a conformance suite. A known
identity, successful execution, and agreement with expected results are
separate evidence and do not prove the full specification.

GitHub Actions runs the same generic CLI; the workflow does not define WEXP
semantics. It uses least-privilege read permissions and exact action commit
pins. Ordinary checks require neither secrets nor a private development
repository.

## Repository map

```text
src/wexp_ref/core00/      first-slice evaluator and exact package driver
src/wexp_ref/runner/      CI-neutral argv runner and observation producer
src/wexp_ref/locks.py     immutable vector-lock validation
src/wexp_ref/cli.py       command-line interface and XML parse/hash check
config/                   exact vector dependency identity and execution scope
schemas/                  runner-specific plan, observation, and lock schemas
examples/                 generic development-only runner plan
provenance/               public genesis inventory and non-claims
scripts/                  local validation and Action-pin checks
tests/                    generic runner and lock tests
```

## Licensing

Repository-authored reference implementation software and tooling are licensed
under the [Apache License 2.0](LICENSE) unless explicitly stated otherwise.
WEXP specifications remain separately authoritative and are not licensed by
this software license merely because the implementation refers to them.

## Public genesis

The [public genesis manifest](provenance/PUBLIC-GENESIS.json) inventories the
files in this repository's first authorized public commit. That root commit
does not imply that the included work was created or first published at that
time.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for contribution and review guidance.
