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
`harness_error` on stderr and exits 2 without a Core result. The CLI limit is
4 MiB per input file. Do not equate process success with an accepted claim.

## Reproduce the bounded corpus run

Use a new build directory, because outputs are created exclusively:

```sh
git clone https://github.com/WEXP-dev/wexp-vectors.git build/core02-vectors
git -C build/core02-vectors checkout --detach 2e6b6da1d77b7fa8bb618b9fb8af0817573f70cf
python scripts/verify_core02_corpus.py --repository build/core02-vectors
python build/core02-vectors/vectors/WEXP-CORE-02-VECTORS-001/verify.py
python build/core02-vectors/vectors/WEXP-CORE-02-VECTORS-001/corpus.py --check --output build/core02-inputs.json
python -m wexp_ref.core02.qualify --corpus build/core02-inputs.json --expected-sha256 d5d2c9d54185f04ac59ac2b5642853a6ebd00c3d28a3239d62682186f5df323f --output build/core02-report.json
python -O -m wexp_ref.core02.qualify --corpus build/core02-inputs.json --expected-sha256 d5d2c9d54185f04ac59ac2b5642853a6ebd00c3d28a3239d62682186f5df323f --output build/core02-optimized-report.json
python -m unittest discover -s tests -p 'test_core02_*.py' -v
```

The external lock is checked before the corpus's expectation builders execute.
The qualifier checks the expanded JSON digest again before decoding it. The
corpus never derives expected outputs from this implementation. Record the exact
implementation commit and interpreter alongside the output report.

The core module derives from same-project preparation reviewed against the posted
contract. No historical proof or private test count is promoted into a new public
qualification result. Source changes and new runs have their own identities.
