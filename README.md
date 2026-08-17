# WEXP Reference Implementation

WEXP (Witnessed Execution Protocol) is an IETF-oriented specification effort
for evaluating support for claims about software and AI execution within
explicit evidence and observation boundaries.

This repository contains the WEXP reference implementation and related test
tools, as a Python 3.12+ package. It qualifies the posted Core `-01`
specification with two structurally independent engines and a comparator, runs a
small revision-scoped Core `-00` vector slice, checks XML parsing and the
`wexp-vectors` dependency lock, and provides a generic execution runner.

> The WEXP specifications are authoritative. This implementation does not
> define WEXP.

The package is pre-alpha. Passing one of its checks does not prove protocol
correctness, interoperability, conformance by an independent implementation,
IETF acceptance, or the validity of an execution claim.

## Relationship to the specifications

The current WEXP specification is
[Core `-01`](https://datatracker.ietf.org/doc/draft-sergeev-wexp-core/01/),
an Internet-Draft posted 2026-08-17; Core `-00` remains available as the previous
revision. Neither is an Internet Standard. The reference implementation may lag behind the specifications.
A missing feature here does not mean that it is absent from a specification.
This implementation cannot add, replace, or reinterpret specification
requirements. Pre-publication development is maintained separately.

## WEXP repositories

- [Specifications — `wexp-spec`](https://github.com/WEXP-dev/wexp-spec) —
  published WEXP specifications and their provenance. **Authoritative.**
- [Test vectors — `wexp-vectors`](https://github.com/WEXP-dev/wexp-vectors) —
  vectors derived from those specifications, with their schemas and validators.
- [Reference implementation — `wexp-ref`](https://github.com/WEXP-dev/wexp-ref) —
  this repository. It **consumes** the vectors at a pinned commit and never
  defines an expected outcome.

The direction is one-way and does not reverse:

```text
WEXP specifications -> vectors -> this implementation
```

If this implementation and a vector disagree, this implementation is wrong until
the specification says otherwise.

## Available

The CLI currently provides:

- Core `-01` qualification (`python3 -m wexp_ref.core01.harness.orchestrate`):
  run both independent engines and the comparator over the pinned Core `-01`
  vector corpus;
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

## Core-01 qualification

`src/wexp_ref/core01/` runs two structurally independent engines and a
comparator over the WEXP Core-01 vector corpus.

The corpus is **not** vendored here. It is fetched from the exact
`WEXP-dev/wexp-vectors` commit pinned in `config/wexp-vectors-core01.lock.json`,
and the fetched manifest digest must match the lock before anything executes.
Expected outcomes come from that corpus, which transcribes them from the
published Internet-Draft. Engine output is never the source of an expectation —
if an engine and a vector disagree, the engine is wrong until the specification
says otherwise.

### Independence

The two engines share no semantic module. `independent` works in set algebra over
keyed support entries with a guard-callable ingress; `reference` works in bitmask
arithmetic over ordered record accumulation with a numbered position table. A
firewall test walks their imports and fails if either reaches into the other or
into anything outside the small shared harness. The comparator is the only
expectation-aware component.

### Running it

    pip install -e .

    # Fetch the exact corpus commit this repository pins. Never track a branch:
    # the lock is what makes a result reproducible.
    COMMIT=$(python3 -c 'import json;print(json.load(open("config/wexp-vectors-core01.lock.json"))["commit"])')
    git clone https://github.com/WEXP-dev/wexp-vectors build/wexp-vectors
    git -C build/wexp-vectors checkout "$COMMIT"

    PYTHONPATH=src python3 -m wexp_ref.core01.harness.orchestrate \
      --candidate build/wexp-vectors/vectors/WEXP-CORE-01-VECTORS-001 \
      --output build/qualification/portable \
      --environment portable

    WEXP_CORE01_CORPUS=build/wexp-vectors/vectors/WEXP-CORE-01-VECTORS-001 \
      PYTHONPATH=src python3 -m unittest discover -s tests -t . -p 'test_core01_*.py'

Without `WEXP_CORE01_CORPUS` the corpus-dependent tests skip rather than pass
silently.

### Public matrix

[`core01-qualification.yml`](.github/workflows/core01-qualification.yml) runs the
set in three declared environments and then compares them:

| Environment | Runner | Kind |
|---|---|---|
| `portable` | `ubuntu-latest` | host Python, no container, no platform requirement |
| `docker` | `ubuntu-latest` | pinned `linux/amd64` image, digest-locked |
| `darwin` | `macos-15` | native macOS arm64 |

Scheduling is owned by
[`matrix_policy.py`](src/wexp_ref/core01/tools/matrix_policy.py) rather than
buried in a workflow expression: a push runs `portable` only, while a pull
request or manual dispatch runs the full matrix plus the portability comparison.
**A portable-only push result is not evidence of qualification readiness**; that
needs a complete full-matrix observation at one exact head.

The comparison asserts that the engine payload digests, the comparison summary
and the candidate identity are identical across environments. Anything
environment-specific — interpreter build, machine, filesystem case sensitivity —
is recorded but deliberately excluded from that claim.

### When the matrix passed, and when it did not

The two states must not be collapsed:

- **At Core-01 publication time** the hosted cross-platform matrix was
  `DEFERRED — INFRASTRUCTURE UNAVAILABLE`. It was **not** a pass, and was
  deliberately never recorded as one. The publication candidate
  `PC-core-01-001` was issued on that basis.
- **After publication**, once the tooling was public and public runners were
  available, the full matrix completed **PASS** — the current state shown above.

The later pass does not retroactively alter `PC-core-01-001` or the
publication-time qualification state, and it is not a prerequisite attached to
revision 01 after the fact. It is recorded as
`POST-PUBLICATION COMPLETION OF DEFERRED EVIDENCE`.

### What a pass means

Sixteen transcribed expectations were met by two independent implementations in
every declared environment. It is not certification, conformance, or endorsement.

### GAP-0014 — single-read artifact loading

**FIXED POST-PUBLICATION IN WEXP-REF.**

Earlier revisions of this loader could hash one filesystem read and parse a
second, independent read of the same path. Under a concurrent writer the digest
recorded in an evidence bundle could therefore describe bytes that were never
evaluated. Verdicts were unaffected; the integrity of the evidence identity was
not.

`canonical.read_artifact()` now reads a path exactly once and binds its bytes,
digest and size together; `Artifact.json()` parses that same buffer. The helpers
that digested or measured a path independently of whoever parsed it were removed
rather than kept, so the invariant is structural rather than a convention.

What this does **not** say:

- it does not say the private pre-publication harness had been fixed;
- it does not say the publication-time qualification used this corrected loader;
- it does not change `PC-core-01-001`, the published Core-01, the vector corpus
  or any expected outcome.

The fix changes no recorded value: engine payload digests and the evidence bundle
digest are byte-identical before and after.

## Repository map

```text
src/wexp_ref/core01/      Core -01 qualification: harness, two independent
                          engines, comparator, declared environments, schemas
src/wexp_ref/core00/      first-slice evaluator and exact package driver
src/wexp_ref/runner/      CI-neutral argv runner and observation producer
src/wexp_ref/locks.py     immutable vector-lock validation
src/wexp_ref/cli.py       command-line interface and XML parse/hash check
config/                   exact vector dependency identities, including the
                          pinned Core -01 corpus lock
docker/                   pinned linux/amd64 image for the container environment
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
