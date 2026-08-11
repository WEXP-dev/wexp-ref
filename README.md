# WEXP Reference Implementation

WEXP (Witnessed Execution) is an IETF-oriented specification effort for
independently verifiable claims about software and AI execution. Evidence and
observation boundaries limit which claims the available evidence can support.

This repository is for the WEXP reference implementation and related test
tools. The current Python 3.12+ package checks XML parsing and the
`wexp-vectors` dependency lock and provides a generic execution runner.

> The WEXP specifications are authoritative. This implementation does not
> define WEXP.

The package is pre-alpha. Passing one of its checks does not prove protocol
correctness, interoperability, conformance by an independent implementation,
IETF acceptance, or the validity of an execution claim.

## Relationship to the specifications

The only WEXP specification currently published is the historical
[Core `-00`](https://datatracker.ietf.org/doc/html/draft-sergeev-wexp-core-00)
Internet-Draft. The reference implementation may lag behind the specifications.
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

- `validate-xml`: parse an XML file and report its SHA-256 digest;
- `validate-lock`: check whether the `wexp-vectors` dependency lock is pinned
  or explicitly blocked; and
- `run`: execute a declarative argv-only plan and record observations.

These commands do not parse, emit, or semantically verify a WEXP protocol
record. A successful XML parse does not establish conformance with WEXP or IETF
acceptance. Lock validation checks dependency metadata only; it neither
executes vectors nor proves protocol correctness.

## Current limitations

- The package does not yet implement the Core `-00` verification model.
- No normative WEXP vector package has been released. The dependency lock is
  marked `blocked`, and CI does not download or run vectors.
- The runner is not a sandbox. Its observations are specific to this
  implementation, not standardized WEXP records or evidence of conformance.

## Local use

The package has no runtime dependencies:

```sh
python3 -m pip install --no-deps .
wexp-ref --version
wexp-ref validate-lock
wexp-ref validate-xml path/to/document.xml
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

## Reproducibility and vectors

The checked-in vector lock is marked `blocked` without a guessed commit or
digest. The workflow does not download or run vectors, and it does not report
cross-repository vector execution as PASS.

After a vector package is released, its immutable identity and manifest digest
can be pinned before the workflow is extended to acquire and run it. A known
identity and actual execution remain separate evidence.

GitHub Actions runs the same generic CLI; the workflow does not define WEXP
semantics. It uses least-privilege read permissions and exact action commit
pins. Ordinary checks require neither secrets nor a private development
repository.

## Repository map

```text
src/wexp_ref/runner/      CI-neutral argv runner and observation producer
src/wexp_ref/locks.py     vector-lock validation
src/wexp_ref/cli.py       command-line interface and XML parse/hash check
config/                   vector dependency status
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
