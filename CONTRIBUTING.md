# Contributing to `wexp-ref`

`wexp-ref` is an implementation and test vehicle. Its behavior must not define
WEXP.

Developers should be able to implement and test WEXP from published
specifications and released implementation-independent vectors without treating
`wexp-ref` as authoritative. Vector expectations must come from specification
requirements, not from this repository's output.

## Relationship to published specifications

Before adding behavior that claims to implement WEXP semantics:

1. Identify an intentionally published specification revision and the exact
   requirement that supports the behavior.
2. Confirm that the public API and tests do not disclose rules from an
   unpublished revision, representation, profile, or mapping.
3. Classify disagreements as implementation defects or specification
   ambiguities; do not resolve them by declaring the implementation normative.
4. Keep pre-publication implementation work outside this repository.
5. Add tests for supported behavior and prohibited inferences only after the
   governing specification has been published.

The implementation may lag behind the specifications. Missing code does
not remove a specification requirement, and passing code does not create one.

## Validation

Use Python 3.12 or later:

```sh
python3 -m pip install --no-deps .
python3 scripts/validate_repository.py
actionlint
```

When working without installation, use `PYTHONPATH=src`.

No normative WEXP vector package has been released, so the checked-in lock is
marked `blocked`. Before CI can run an intentionally released normative vector
package, the package must have an immutable identity and the workflow must use
a reviewed step to acquire and execute it. Never report an unexecuted check as
PASS. Floating revisions such as `main`, `latest`, or `HEAD` must not appear in
evidence.

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
