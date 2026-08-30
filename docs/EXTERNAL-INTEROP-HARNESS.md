# External Interop Harness

This tooling automates only the evidence envelope around an external-protocol interoperability exercise. It does not infer protocol semantics and it does not compare semantic results.

## v0.1 model

The human/auditable lifecycle may be described as `PIN -> FREEZE -> COMMIT -> REVEAL -> VERIFY -> RECORD`, but the public CLI deliberately exposes only two operations:

```sh
wexp-ref interop prepare \
  --source-lock source-lock.json \
  --fixtures neutral-fixtures.zip \
  --reading frozen-reading.json \
  --output commitment.json

wexp-ref interop verify \
  --commitment commitment.json \
  --source-lock source-lock.json \
  --source-root path/to/pinned/checkout \
  --fixtures neutral-fixtures.zip \
  --reading revealed-reading.json \
  --output verification.json
```

`prepare` hashes exact file bytes. There is no private JSON canonicalization scheme. Whitespace changes in a reading intentionally change its commitment.

A source lock names a repository, a full Git commit SHA, and the selected source material paths with SHA-256 digests. `verify` checks the revealed source-lock, fixture and reading bytes against the commitment and checks the selected source materials against the lock.

The Git commit is recorded as provenance. The selected material digests are the byte-level evidence checked by this tool. Neither establishes that the source text is true or that a reading of it is semantically correct.

## Threats covered in v0.1

- reading mutation after commitment;
- fixture substitution after commitment;
- source-lock substitution after commitment;
- selected source-artifact substitution;
- path traversal outside the declared source root.

## Explicit non-goals

v0.1 does not:

- derive WEXP normalized inputs from a peer protocol;
- map lifecycle labels to WEXP bases, qualifiers, or verdicts;
- compare two readings;
- repair disagreement or underdetermination;
- prove author identity merely from a SHA-256 value;
- prove two authors or implementations were independent;
- define a WEXP wire format or Native Record;
- implement SLSA, in-toto, or Sigstore attestations.

The design borrows their useful invariants — content-addressed materials, immutable evidence, and separation of provenance from semantic truth — without importing a supply-chain attestation stack before there is a demonstrated need.

## Generalization gate

The first use is WEXP x EMILIA. Its experiment-specific readings and comparator stay outside generic public tooling until the reveal is complete. A generic semantic comparison abstraction should not be added until a second external protocol exercise demonstrates that the same abstraction is genuinely reusable.
