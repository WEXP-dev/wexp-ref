# WEXP Reference Implementation

Version-scoped reference implementations and test tools for published WEXP
specifications. The specifications, not this code or its output, are authoritative.
WEXP appraises support for execution-related claims within explicit evidence and
observation boundaries; it does not certify truth, safety, authority or alignment.

The package is pre-alpha, requires Python 3.12 or newer, and has no runtime
package dependencies. Select the semantic version explicitly. A newer document,
repository name, or successful CI job does not upgrade a historical result.

## Implementations and exact scope

| Component | Contract | Entry point and limits |
|---|---|---|
| `wexp_ref.core02` | Posted Core-02, `wexp-core-2` | [Run and reproduce](docs/core02.md); [bounded surface declaration](CORE02-CONFORMANCE.md). Complete-result comparison against a separately pinned 89-case corpus; not a full-conformance claim. |
| `wexp_ref.core01` | Core-01 | [Detailed historical guide](CORE01-GUIDE.md#core-01-qualification); [PARTIAL conformance declaration](CONFORMANCE.md). Existing engines and corpus locks are retained. |
| `wexp_ref.core00` | Core-00 | [First-slice guide](CORE01-GUIDE.md#core-00-vector-slice). Revision-scoped abstract harness, not a wire-format verifier. |
| Generic runner | Local runner contract | [Usage and security limits](CORE01-GUIDE.md#generic-runner). Records observations; it is not a sandbox. |
| WEXP Coverage | Separate Coverage-00 contract | Not implemented or qualified by these Core modules. No `pg-ledger/0.2.0` runtime result is established here. |

The current specification is
[WEXP Appraisal Core-02](https://datatracker.ietf.org/doc/draft-sergeev-wexp-core/02/).
[Coverage-00](https://datatracker.ietf.org/doc/draft-sergeev-wexp-coverage/00/)
is a separate individual Internet-Draft. Neither is an Internet Standard or
working-group endorsement. The repository may lag behind a published contract;
read the declaration for the particular module rather than inferring completeness.

## Core-02 quick start

```sh
python -m pip install --no-deps .
python -m wexp_ref.core02 --input normalized-input.json --profiles profiles.json
```

The API is `from wexp_ref.core02 import appraise`. It consumes already normalized
logical input and an explicitly supplied profile catalog. It does not authenticate
raw evidence or establish that a producer's statement is true. Its local JSON
harness is not a standardized WEXP carrier.

A successfully emitted Core appraisal contains all twenty components, including
`reject` results. File, JSON and harness-limit failures instead produce a separate
error and no Core appraisal. Process exit status is not the claim verdict.

For corpus generation, exact source pins, complete-result comparison and normal/
optimized runs, follow [the reproduction instructions](docs/core02.md). The
[Core-02 workflow](.github/workflows/core02-qualification.yml) installs this
package and checks Python 3.12 and 3.13. Consult the actual run at the selected
commit; a workflow file is not evidence that its checks ran.

## Historical tooling remains reproducible

The previous README is preserved byte-for-byte as
[`CORE01-GUIDE.md`](CORE01-GUIDE.md), with all original commands, Windows guidance,
qualification distinctions, limitations and dependency identities. Its Core-01
statements describe that historical surface, not the added Core-02 module.

The existing `wexp-ref` CLI remains revision-scoped:

```sh
wexp-ref --version
wexp-ref validate-lock
wexp-ref validate-xml path/to/document.xml
wexp-ref core00-run-vectors path/to/exact/wexp-vectors --output build/core00-results.json
```

For the Core-01 `new_candidate` tool, `--output` names the **parent** directory.
It creates `<output>/<candidate_id>`, and the resulting candidate directory basename must
equal the descriptor's `candidate_id`. For example, a seed with ID `MY-CANDIDATE`
and `--output build/candidates` produces `build/candidates/MY-CANDIDATE`.
This is an enforced harness-layout invariant, not a new Core semantic rule.
See [the full Core-01 recipe](CORE01-GUIDE.md#evaluating-your-own-example).

The Core-01 engines, fixed dependency locks, historical test expectations and
qualification records were not rewritten by the Core-02 addition. Structural
separation of same-project engines is not external independent validation.

## Development checks

```sh
python -m pip install --no-deps .
python scripts/validate_repository.py
python -m unittest discover -s tests -p 'test_core02_*.py' -v
```

From a source checkout without installation, set `PYTHONPATH=src`. The ordinary
repository validation and revision-specific qualification workflows are separate.
Tests needing an external corpus must identify whether they ran or skipped.
A local unit-test pass alone is not a full qualification matrix observation.

## Authority and repositories

```text
published specifications -> reviewed requirements -> frozen expectations -> implementation results
```

- [Appraisal Core specifications](https://github.com/WEXP-dev/wexp-appraisal-core-spec): exact published revisions and provenance.
- [Coverage specification](https://github.com/WEXP-dev/wexp-coverage-spec): separate population and correspondence claims.
- [Test vectors](https://github.com/WEXP-dev/wexp-vectors): independently consumable, specification-derived expectations; no dependency on this implementation.
- [Interop records](https://github.com/WEXP-dev/wexp-interop): exact historical experiment packages and their limits. Core-01 experiments are not reclassified as Core-02 results.

The new Core-02 module and corpus do not establish an AAC mapping, a new WIMSE
experiment, cross-carrier equivalence, or Coverage deployment conformance.

## Licensing, provenance and contributions

Repository-authored implementation software and tooling use
[Apache-2.0](LICENSE) unless otherwise stated. Referenced Internet-Drafts retain
their own notices and are not relicensed by this software license.
[The public genesis inventory](provenance/PUBLIC-GENESIS.json) remains historical
and does not imply later additions existed at the initial publication.

See [CONTRIBUTING.md](CONTRIBUTING.md). Passing tests does not grant certification,
IETF acceptance, independent implementation conformance or policy authority.
