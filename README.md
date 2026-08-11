# WEXP Public Reference Tooling

This repository contains the public WEXP reference tooling state: a deliberately
conservative Python 3.12+ command-line package, non-normative XML parse and hash
checks, public vector-dependency lock validation, and a GitHub-neutral execution
runner. Experimental or unreleased development may occur separately.

> The WEXP specifications are authoritative.
>
> This repository is an implementation and test vehicle. It does not define
> WEXP or create specification semantics.

The implementation is pre-alpha. A passing check is not proof of protocol
correctness, independent conformance, interoperability, IETF acceptance, or
correctness of an action being described.

## Published-specification boundary

Public implementation behavior in this repository is limited to intentionally
published WEXP specification states. The currently published repository state
includes historical Core `-00`; this tree does not currently provide a semantic
implementation of that revision.

Public implementation coverage may lag the specifications. Absence of a feature
here does not imply that the feature is absent from a specification, and
implementation behavior does not add, replace, or reinterpret specification
requirements. Implementation experiments for unpublished behavior are kept
outside this public repository state.

## Public tooling surface

The CLI currently provides:

- `validate-xml`: parse an XML artifact and report its SHA-256 digest;
- `validate-lock`: validate an immutable or explicitly blocked public-vector
  dependency state; and
- `run`: execute a reviewed declarative argv-only plan and record observations.

These commands do not parse, emit, or semantically verify a WEXP protocol
record. XML parsing establishes neither specification validity nor IETF
acceptance. Lock validation establishes dependency metadata consistency, not
vector execution or protocol correctness.

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
steps, outputs, source/dependency identities, claims, and non-claims. Commands
are passed directly to `subprocess.run(..., shell=False)`; `{python}` and
`{workspace}` are the only whole-argument substitutions. The runner hashes
declared inputs and observed output files and records timestamps, argv,
stdout/stderr hashes, observations, and exit statuses.

```sh
PYTHONPATH=src python3 -m wexp_ref run \
  examples/runner-smoke-plan.json \
  --workspace . \
  --record WEXP-REF-RUNNER-OBSERVATION.json
```

The runner is not a sandbox. A reviewed plan can execute any declared program
available to the caller; it records declared files but cannot prove that a
process touched no other resource. Plans should therefore be reviewed and run
with least privilege.

Observations emitted by the example command use
`record_kind: wexp-ref-runner-observation`. They are implementation-local
development infrastructure, not a standardized WEXP protocol record or
evidence of protocol conformance.

Every emitted record includes required non-claims that it does not establish
IETF acceptance, independent implementation conformance, complete WEXP
correctness, or standardized protocol-record status.

## Reproducibility and vectors

No released public normative WEXP vector package is currently available. The
checked-in vector lock therefore records an explicit `blocked` state without a
guessed commit or digest. The public workflow does not fetch or execute vectors,
and cross-repository vector execution is not reported as PASS.

When a released vector package becomes available, its immutable identity and
manifest digest can be pinned before acquisition and execution are added. A
known identity and actual execution remain separate evidence.

GitHub Actions orchestrates the same generic CLI. It is not a semantic source
of truth. The workflow uses least-privilege read permissions and exact action
commit pins; ordinary checks do not require secrets or a private development
repository.

## Repository map

```text
src/wexp_ref/runner/      CI-neutral argv runner and evidence producer
src/wexp_ref/locks.py     public vector-lock validation
src/wexp_ref/cli.py       command-line interface and XML parse/hash check
config/                   public vector-dependency status
schemas/                  implementation-local plan, observation, and lock schemas
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
