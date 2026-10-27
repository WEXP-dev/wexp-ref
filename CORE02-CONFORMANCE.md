# Core-02 implementation surface and qualification limits

`wexp_ref.core02` is a version-scoped implementation of the normalized-input
appraisal procedure in posted `draft-sergeev-wexp-core-02`, semantics `wexp-core-2`.
It is separate from the historical Core-01 implementation and its
[conformance record](CONFORMANCE.md). No prior Core-01 result is transferred.

## Implemented surface

The module provides ordered ingress classification; profile-catalog and
cross-field validation; exact support and qualifier subsets; the Boundary
Ceiling; structural maxima and relations; per-claim counter-evidence; diagnostic
and limitation projection; and all twenty logical result components, including
the fixed rejection projection. The JSON representation uses exact text atoms,
ordered scoped-atom pairs, unordered logical sets, and null for unavailable.
The supplied profile catalog and prior normalization remain caller premises.

A malformed extension pair is rejected at structural ingress before profile
binding, as required by sections 6.2 and 12. A well-formed unbound pair instead
produces a mapping error. This distinction differs from the earlier private
preparation implementation and is exercised by posted-contract controls.

## What the qualification demonstrates

The separate public corpus is pinned by
[`config/wexp-vectors-core02.lock.json`](config/wexp-vectors-core02.lock.json).
It contains 16 normative C01-C16 transcriptions and 73 non-normative derived
controls. Qualification compares all twenty result components and verifies that
inputs and the profile catalog were not changed. Forty-two negative comparator
controls include omitted/changed components and Boolean-to-number substitutions.

The dedicated CI installs this package, reads the exact corpus commit from the
lock and checks the frozen public `corpus.json` on Python 3.12 and 3.13 in
normal and optimized modes, without executing the corpus's expectation code. Only an actually successful
run at an identified commit is evidence of those checks. A workflow definition
alone is not a test result. Run reports contain exact source/corpus digests and
all observed appraisals; review the run and its jobs, not just a badge.

This is bounded author-side qualification, not a designation of the corpus as a
conformance suite or a claim of complete Core conformance. No external independent
implementation or review is established. Known-source expectations and same-project
implementation work limit the independence of the evidence.

## Excluded surfaces

No raw carrier parsing or cryptographic authentication, evidence discovery,
recorder-control verification, real-world action truth, mapping-profile execution,
composition-profile execution, arbitrary profile-defined atom normalization,
application reliance decision, Coverage evaluator, PostgreSQL profile validation,
or AAC/WIMSE interoperability is established by this module or corpus.

The local CLI rejects malformed JSON, duplicate object keys, non-finite numbers
(including exponent overflow such as `1e9999`) and local size-limit violations
before Core invocation. Those failures produce no Core appraisal.
A decoded logical input may produce a complete Core rejection; that is a separate
outcome. Resource and Python object limits are not new normative Core semantics.
The public specification remains authoritative if the implementation is wrong.
