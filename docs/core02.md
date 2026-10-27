# Run the posted Core-02 appraisal module

Read [the surface and limits](../CORE02-CONFORMANCE.md) before interpreting a pass.
This module does not change or silently select the historical Core-01 engine.
Python 3.12 or newer is required. No private repository is a dependency.

## Install and evaluate a normalized input

From a checkout of this repository:

```sh
python -m pip install --no-deps .
python -m wexp_ref.core02 --input normalized-input.json --profiles profiles.json
```

The API is `from wexp_ref.core02 import appraise`, followed by
`appraise(normalized_input, profiles)`. Profiles map exact immutable identities to
`tokens`, `relation_tokens` and `scope_names`. The corpus documentation describes
this local non-normative JSON harness. Profile identity resolution and evidence
normalization must be performed and justified before calling the appraiser.

The CLI emits all twenty result components on stdout, with exit code 0, including
a valid Core rejection. A file/JSON/catalog-envelope error emits a separate
`harness_error` on stderr and exits 2 without a Core result. This includes
duplicate object members, `NaN`/`Infinity` constants and numbers whose exponent
overflows the local floating-point type (for example `1e9999` or `-1e9999`).
A decoded but logically malformed input instead yields the full Core rejection.
The CLI limit is 4 MiB per input file. Do not equate process success with an
accepted claim.

## Reproduce the bounded corpus run

The exact public corpus commit and manifest digest are recorded in
[`config/wexp-vectors-core02.lock.json`](../config/wexp-vectors-core02.lock.json).
Check out exactly that commit; use a new results directory, because outputs are
created exclusively:

```sh
git clone https://github.com/WEXP-dev/wexp-vectors.git build/core02-vectors
git -C build/core02-vectors checkout --detach "$(python -c "import json;print(json.load(open('config/wexp-vectors-core02.lock.json'))['commit'])")"
python -m pip install --no-deps .
python scripts/verify_core02_corpus.py --repository build/core02-vectors
python scripts/qualify_core02_locked.py --vectors build/core02-vectors --output-dir build/core02-results
python -m unittest discover -s tests -p 'test_core02_*.py' -v
```

`qualify_core02_locked.py` requires a clean checkout at the locked commit,
checks the manifest and frozen `corpus.json` digests from the lock, and runs the
full-result comparison in normal and optimized (`-O`) modes. It reads the frozen
data only; it never imports the corpus's expectation generators. The qualifier
checks the corpus digest again before decoding it. The corpus never derives
expected outputs from this implementation. Record the exact implementation
commit and interpreter alongside the output reports.

The core module derives from same-project preparation reviewed against the posted
contract. No historical proof or private test count is promoted into a new public
qualification result. Source changes and new runs have their own identities.
