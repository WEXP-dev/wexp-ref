# Contributing to `wexp-ref`

`wexp-ref` is an implementation and test vehicle. A change must not make
implementation behavior a hidden source of WEXP meaning.

External developers should be able to implement and test WEXP using published
specifications and released implementation-independent vectors without treating
`wexp-ref` as an authority. Vector expectations must come from specification
requirements, not from this repository's output.

## Published-specification boundary

Before adding behavior that claims to implement WEXP semantics:

1. Identify an intentionally published specification revision and the exact
   requirement that supports the behavior.
2. Confirm that the public API and tests do not disclose rules from an
   unpublished revision, representation, profile, or mapping.
3. Classify disagreements as implementation defects or specification
   ambiguities; do not resolve them by declaring the implementation normative.
4. Keep experimental or unreleased implementation work outside the public
   repository state.
5. Add tests for supported behavior and prohibited inferences only after the
   governing specification state is public.

Public implementation coverage may lag the specification. Missing code does
not remove a specification requirement, and passing code does not create one.

## Validation

Use Python 3.12 or later:

```sh
python3 -m pip install --no-deps .
python3 scripts/validate_repository.py
actionlint
```

When working without installation, use `PYTHONPATH=src`.

No released public normative WEXP vector package is currently available. The
checked-in dependency state is therefore explicitly blocked. A future public
vector test requires both an immutable released identity and an actual
acquisition and execution step. An unexecuted check must never be reported as
PASS, and floating revisions such as `main`, `latest`, or `HEAD` must not appear
in evidence.

## Runner and security

Runner plans execute reviewed argv arrays without a shell, but the runner is not
a sandbox. Keep commands deterministic where practical, declare every relevant
input/output, avoid secrets, and use least privilege. Do not add a GitHub API
dependency to the generic runner. GitHub-specific orchestration belongs only in
workflow files.

Third-party Actions must be pinned to exact 40-character commit SHAs. Run
`python3 scripts/check_action_pins.py` after workflow changes.

Unless explicitly documented otherwise, contributions are submitted under the
repository's Apache License 2.0. No contributor license agreement, copyright
assignment, or sign-off requirement is introduced by this statement.
