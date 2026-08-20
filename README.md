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
`cda36a36dcc1b66209e3781a26aa2a0d05e665ea` and manifest SHA-256
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

On Linux or macOS:

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

### Windows PowerShell 5.1

These commands are tested as Windows PowerShell commands. Start in the directory
where you want the two repositories, with Git for Windows and Python 3.12 or
newer installed. The supported path is an ordinary clone; do not disable
`core.autocrlf` for it.

```powershell
$ErrorActionPreference = "Stop"

function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

git clone https://github.com/WEXP-dev/wexp-ref.git
Assert-NativeSuccess "clone wexp-ref"
Set-Location wexp-ref
$RepoRoot = (Get-Location).Path

python -m pip install --disable-pip-version-check --no-deps -e .
Assert-NativeSuccess "install wexp-ref"

# An editable install makes this unnecessary, but this is the PowerShell 5.1
# equivalent of PYTHONPATH=src for running directly from a source checkout.
$env:PYTHONPATH = Join-Path -Path $RepoRoot -ChildPath "src"

$LockPath = Join-Path -Path $RepoRoot -ChildPath "config\wexp-vectors-core01.lock.json"
$Lock = Get-Content -LiteralPath $LockPath -Raw | ConvertFrom-Json
$VectorsPath = Join-Path -Path $RepoRoot -ChildPath "build\wexp-vectors"

git clone https://github.com/WEXP-dev/wexp-vectors.git $VectorsPath
Assert-NativeSuccess "clone wexp-vectors"
git -C $VectorsPath checkout --detach $Lock.commit
Assert-NativeSuccess "check out the locked wexp-vectors commit"

python scripts\verify_core01_corpus.py --lock $LockPath --repository $VectorsPath
Assert-NativeSuccess "verify the locked commit and manifests"

$QualificationRoot = Join-Path -Path $RepoRoot -ChildPath "build\qualification\windows"
$Sets = @("WEXP-CORE-01-VECTORS-001", "WEXP-CORE-01-VECTORS-002")
foreach ($Set in $Sets) {
    $Candidate = Join-Path -Path $VectorsPath -ChildPath "vectors\$Set"
    python -m wexp_ref.core01.harness.orchestrate `
        --candidate $Candidate `
        --output $QualificationRoot `
        --environment windows
    Assert-NativeSuccess "qualify $Set"
}
```

Inspect one Set 001 vector:

```powershell
$Set001 = Join-Path -Path $VectorsPath -ChildPath "vectors\WEXP-CORE-01-VECTORS-001"
python -m wexp_ref.core01.tools.inspect_vector `
    --candidate $Set001 `
    --vector C06
Assert-NativeSuccess "inspect C06"
```

The identities used by those commands can be read without Unix utilities:

```powershell
$RefCommit = git rev-parse HEAD
Assert-NativeSuccess "read wexp-ref commit"
$VectorsCommit = git -C $VectorsPath rev-parse HEAD
Assert-NativeSuccess "read wexp-vectors commit"

"wexp-ref commit: $RefCommit"
"wexp-vectors commit: $VectorsCommit"
$Lock.vector_sets | Format-Table candidate_id, manifest_path, manifest_sha256, vector_set_sha256
foreach ($Entry in $Lock.vector_sets) {
    $Manifest = Join-Path -Path $VectorsPath -ChildPath $Entry.manifest_path
    Get-FileHash -LiteralPath $Manifest -Algorithm SHA256
}
```

For the fail-closed tamper demonstration, mutate a copy, never the clean corpus.
The copy retains the candidate basename required by the loader. The helper uses
absolute paths internally, validates the file and index before writing, and
prints success only after it verifies the written byte.

```powershell
$Set001 = Join-Path -Path $VectorsPath -ChildPath "vectors\WEXP-CORE-01-VECTORS-001"
$TamperParent = Join-Path -Path $RepoRoot -ChildPath (
    "build\tamper-" + [System.Guid]::NewGuid().ToString("N")
)
New-Item -ItemType Directory -Path $TamperParent | Out-Null
$TamperCandidate = Join-Path -Path $TamperParent -ChildPath "WEXP-CORE-01-VECTORS-001"
Copy-Item -LiteralPath $Set001 -Destination $TamperCandidate -Recurse

$RelativeVector = "vectors\WEXP-CORE-01-Q001-TV-0001.json"
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File scripts\windows_tamper_demo.ps1 `
    -Candidate $TamperCandidate `
    -RelativeFile $RelativeVector `
    -Index 0
Assert-NativeSuccess "mutate the copied vector"

python -m wexp_ref.core01.harness.orchestrate `
    --candidate $TamperCandidate `
    --output (Join-Path -Path $TamperParent -ChildPath "qualification") `
    --environment windows
$TamperExitCode = $LASTEXITCODE
if ($TamperExitCode -eq 0) {
    throw "Tampered candidate unexpectedly passed qualification"
}
"EXPECTED FAIL-CLOSED RESULT: tampered candidate exited $TamperExitCode"
```

The final failure is the expected result. It does not prove who or what changed
the file; it proves that qualification did not accept different bytes.

Digest mismatches always remain qualification failures. When a textual file's
observed bytes differ from its declared digest only by LF/CRLF normalization,
the failure also includes a non-authoritative Windows checkout hint. The hint
does not make the bytes equivalent and does not claim whether tampering occurred.

### Public matrix

[`core01-qualification.yml`](.github/workflows/core01-qualification.yml) runs the
two public vector sets in four declared environments and then compares each set:

| Environment | Runner | Kind |
|---|---|---|
| `portable` | `ubuntu-latest` | host Python, no container, no platform requirement |
| `docker` | `ubuntu-latest` | pinned `linux/amd64` image, digest-locked |
| `darwin` | `macos-15` | native macOS arm64 |
| `windows` | `windows-latest` | native Windows x64; vector clone uses `core.autocrlf=true` |

Scheduling is owned by
[`matrix_policy.py`](src/wexp_ref/core01/tools/matrix_policy.py) rather than
buried in a workflow expression: a push runs `portable` only, while a pull
request or manual dispatch runs the full matrix plus the portability comparison.
**A portable-only push result is not evidence of qualification readiness**; that
needs a complete full-matrix observation at one exact head.

For each set, the comparison asserts that the engine payload digests, the
comparison summary and the candidate identity are identical across environments.
Anything environment-specific — interpreter build, machine, filesystem case
sensitivity, or path syntax — is recorded but deliberately excluded from that
claim.

### When the matrix passed, and when it did not

The two states must not be collapsed:

- **At Core-01 publication time** the hosted cross-platform matrix was
  `DEFERRED — INFRASTRUCTURE UNAVAILABLE`. It was **not** a pass, and was
  deliberately never recorded as one. The publication candidate
  `PC-core-01-001` was issued on that basis.
- **After publication**, once the tooling was public and public runners were
  available, the then-declared Linux/macOS matrix completed **PASS**.
- **Windows was added later** as a required native leg after external consumer
  testing found checkout line-ending normalization. A historical Linux/macOS
  pass is not a Windows pass; the current workflow must complete all four legs
  for both sets before claiming the current full-matrix observation passed.

The later pass does not retroactively alter `PC-core-01-001` or the
publication-time qualification state, and it is not a prerequisite attached to
revision 01 after the fact. It is recorded as
`POST-PUBLICATION COMPLETION OF DEFERRED EVIDENCE`.

### Inspecting one vector

Qualification evaluates the whole corpus. To understand a single case:

    PYTHONPATH=src python3 -m wexp_ref.core01.tools.inspect_vector \
      --candidate build/wexp-vectors/vectors/WEXP-CORE-01-VECTORS-001 \
      --vector C06

`--vector` takes either a fixture name (`C06`) or a vector id
(`WEXP-CORE-01-Q001-TV-0006`). It prints the asserted claim, the boundary
ceiling, what the vector expects and why, and what both engines produced. Add
`--json` for machine-readable output. Exit status is `0` only when both engines
agree and both match the expectation.

It makes no semantic decision and cannot change a verdict: expectations come
from the vector, never from an engine.

### Evaluating your own example

You are not limited to the published corpus. A candidate is data — a descriptor,
a profile and vectors — and `new_candidate` materialises one from a seed:

    PYTHONPATH=src python3 -m wexp_ref.core01.tools.new_candidate \
      --seed my-seed.json --output build/candidates

A seed carries `candidate_id`, `authority`, `profile` and `vectors`. The two
seeds under [`src/wexp_ref/core01/seeds/`](src/wexp_ref/core01/seeds/) are
working examples; the profile is where the token registry, the base ordering and
the scope keys live, and the published Core-01 set's
[`profile.json`](https://github.com/WEXP-dev/wexp-vectors/blob/main/vectors/WEXP-CORE-01-VECTORS-001/profile.json)
is the Core-01 registry in full.

`--output` names the **parent** directory. `new_candidate` creates
`<output>/<candidate_id>`, and the resulting candidate directory basename must
equal the descriptor's `candidate_id`. This is an enforced loader invariant, not
just a naming convention; it is a harness package-layout requirement, not a
Core-01 semantic rule. For example, a seed whose ID is `MY-CANDIDATE` with
`--output build/candidates` is evaluated from `build/candidates/MY-CANDIDATE`.

`authority` is how a candidate binds to a specification. Set
`published_specification` to `true` and the harness **requires** the bundled
specification at `snapshot_path` to hash to `xml_sha256` — loading fails closed
before any evaluation if it does not. A candidate that claims no published
specification sets it to `false` and asserts no publication authority.

The tool deliberately does not derive expected results. You author them, from
the specification. Deriving them from an engine would grade the engine against
its own output.

Then evaluate as usual:

    PYTHONPATH=src python3 -m wexp_ref.core01.harness.orchestrate \
      --candidate build/candidates/MY-CANDIDATE \
      --output build/mine --environment portable

#### A worked example: invocation without execution evidence

Suppose a tool invocation was requested and recorded, and nothing captured
whether it ran. Asserting `execution` while the boundary ceiling stands at
`invocation` gives:

    verdict          downgrade
    claim supported  False
    ceiling          invocation

The tooling refuses to elevate the claim past the evidence that was actually
captured. `downgrade` means the asserted claim was not supported and a lower one
may be; `reject` means the claim was inadmissible and nothing is appraised;
`accept` means the asserted claim held. None of these certify that an action was
correct, safe, or aligned — WEXP grades evidentiary strength only.

### Conformance status

`wexp-ref` implements a **declared partial** Core-01 surface. See
[`CONFORMANCE.md`](CONFORMANCE.md) for the enumerated implemented rules, the
enumerated known absences, the three corrected verdict-level deviations, and what
agreement between the two engines does and does not establish.

Do not describe this implementation as full Core-01 conformance.

### What a pass means

The formal gate runs the sixteen Set 001 expectations and the nine Set 002
expectations through two independent implementations in every declared
environment. A pass is not certification, conformance, or endorsement.

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
