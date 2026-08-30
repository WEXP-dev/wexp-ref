# Conformance status

    wexp-ref Core-01 conformance:  PARTIAL

This is a deliberate, enumerated partial surface, not a claim of complete Core
appraisal. Do not describe this implementation as a conformance implementation,
as full Core-01 conformance, or as a complete Core appraisal implementation.

The public Core-01 vector sets are **not a conformance suite**. Passing them
means this implementation agreed with the specification-derived expectations
those sets exercise — sixteen in Set 001 and nine in Set 002. It does not
establish complete Core appraisal or full Core-01 conformance, and the surface
claimed here remains exactly the one enumerated below.

## Implemented

- §4.4 typed claims and the admissible domain, including multi-qualifier states
- §4.5 structural product order, and its exclusion as an exact-support predicate
- §6.2 ingress ordering positions 1–3, the fixed rejection projection, and two of
  the seven cross-field invariant families at position 4: exact target and context
  scope, and the token-category rule — see the known absences for the other five
- §8.1 supported-claim construction over the subsets of Q(b), including the
  requirement that a finding name the same target and evaluation context as the
  appraisal input, with limitation carry-through
- §8.2 counter-evidence blocking, scoped to entries whose affected claims include
  the asserted claim or all-admissible-claims
- §8.4 the accept / downgrade / reject verdict conditions as published, but
  not its finding-reason projection step — see the known absences below
- §8.6 the rows listed under *Diagnostics implemented* below

## Diagnostics implemented

Section 8.6 is a matrix of independent rows. Five of its fifteen distinct tokens
have a role in the profile this implementation is driven by, and those rows are
evaluated individually against their own predicates:

| Row | Token | Predicate as published |
|---|---|---|
| boundary-exceeded | `E_BASE_EXCEEDS_BOUNDARY` | usable boundary with the asserted base deeper than its ceiling |
| asserted-base absence | `E_MISSING_REQUIRED_EVIDENCE` | asserted-base aggregate absent |
| asserted PROV absence | `E_MISSING_REQUIRED_EVIDENCE` | asserted PROV aggregate absent |
| asserted IV absence | `E_MISSING_REQUIRED_EVIDENCE` | asserted IV aggregate absent |
| asserted IV not evaluated | `E_IV_NOT_EVALUATED` (gap) | asserted IV target-binding, semantic, or independence assessment not-evaluated |
| counter-evidence not evaluated | `E_COUNTER_EVIDENCE_NOT_EVALUATED` (gap) | applicable counter entry status not-evaluated |
| counter-evidence unresolved | `E_COUNTER_EVIDENCE_UNRESOLVED` | applicable counter entry status unresolved-material |

The three absence rows carry one token between them, which is why the table has
seven lines and five tokens.

`E_MISSING_REQUIRED_EVIDENCE` is also used as the fallback for the ten rows this
profile cannot name, listed below. That fallback fires only when no row above
already applies: Section 8.6 states that "an absent aggregate triggers only its
absence row" and that "status rows require that aggregate to be present", so a
present aggregate never reaches it.

## Known absences — enumerated

These are absences of a declared partial surface. They are **not** presented as
correct behaviour for the omitted rows, and an implementation claiming a wider
surface would have to implement them.

| Item | Disposition |
|---|---|
| `E_EXACT_CLAIM_NOT_SUPPORTED` collapsed into `E_MISSING_REQUIRED_EVIDENCE` | KNOWN ABSENCE — the seven token roles this profile registers do not include it; a candidate profile registering it would require the distinct token |
| `E_INDEPENDENCE_NOT_ESTABLISHED` collapsed into `E_MISSING_REQUIRED_EVIDENCE` | KNOWN ABSENCE — same reason |
| Ten further §8.6 diagnostic rows unimplemented | KNOWN ABSENCE — outside the seven roles the current profile registers |
| An unaccepted boundary returned as an engine rejection rather than through the §8.6 boundary rows | KNOWN ABSENCE — the §8.6 boundary rows are not implemented, so the condition is surfaced as a rejection rather than silently dropped |
| §6.2 ingress position 5 (supplied fatal conditions) beyond the profile's registered tokens | INTENTIONALLY OUT OF CURRENT PROFILE |
| §6.2 position 4 cross-field families other than exact scope and token category — aggregate cardinality and keys, the counter-evidence sentinel, qualifier combinations, conditional `ceiling_base`, and evaluation-scope consistency with extension-key binding | NOT_IMPLEMENTED — five of the seven families §6.2 names at that position |
| §8.4 projection of registered substantive reasons carried by an asserted-role finding or an exact premise of a support entry | KNOWN ABSENCE — unimplemented on all four routes. Unreachable under this profile, which registers no token that can validly carry it, so no valid input currently observes the omission. Recorded anyway; see below |

None of the above is classified as REQUIRED FOR CLAIMED SURFACE or as an ACTUAL
DEFECT, because this document does not claim the wider surface. Widening the
claim without implementing them would make the claim untrue.

## Corrected verdict-level deviations

An independent clean-room implementation, written from the published
specification without reading either engine, surfaced three deviations that did
change verdicts. All three are corrected, and each has a regression test derived
from the specification text rather than from either implementation:

| Deviation | Published rule | Was | Now |
|---|---|---|---|
| Multi-qualifier state | §8.1 A ranges over the subsets of Q(b); §4.4 admits `(execution,{PROV,IV})` | each qualifier lifted singly, two-qualifier state unreachable | subsets enumerated; the state is constructed |
| Unrelated over-ceiling finding | §8.6 the row requires *a present asserted-base aggregate* deeper than the ceiling | any over-ceiling finding produced `E_BASE_EXCEEDS_BOUNDARY` | only the asserted base does |
| Extra accept condition | §8.4 / Verdict: exact support **and** counter-evidence not blocking | both engines also required an empty diagnostic set | the published two conditions only |

The published Set 001 vectors are unaffected by all three corrections: none of
them carries two qualifiers on one base, an unrelated over-ceiling finding, or an
accept with a non-empty diagnostic set. Their evidence bundle digest is unchanged.

## The finding-reason projection, and why it is listed

§8.4 projects a finding's registered substantive reasons into the result:

> for every boundary, base, or qualifier finding that is the asserted role or an
> exact premise of a SupportEntry: add its registered substantive reasons to
> reasons

§8.6 bounds where those reasons may come from, and names
`E_EVIDENCE_COVERAGE_MISMATCH`, `E_CHAIN_UNBOUND` and
`E_COMPOSITION_WARRANT_MISSING` as tokens that travel this path. Neither engine
implements it, on any of the four routes.

No valid input under this profile can observe that. Of the four substantive tokens
it registers, three name §8.6 matrix rows — and §8.6 says the matrix is exhaustive
and that no condition outside it creates a Core-derived non-fatal token, so a
matrix token has to arrive from its own row rather than from a finding's reason
set. The fourth, `P_COUNTER_FAIL`, has no role mapping and no published
definition; its meaning comes from its name and from its single appearance inside
fixture C15's counter-evidence entry, so attaching it to a base finding would
assert a counter-evidence failure about a base aggregate.

The absence is listed because unreachable is not the same as absent. A profile
registering one suitable token would reach it immediately, and an implementation
claiming a wider surface would have to implement it.

This also bounds what can be demonstrated about the accept condition. Within this
profile, `accept` with a non-empty substantive set is unreachable by any valid
input: every registered §8.6 substantive row implies either that the asserted
claim is not exactly supported or that counter-evidence blocks it, counter-entry
reasons project only from blocking entries, and the finding-reason path has no
usable token. The regression for that property asserts its own precondition and
skips, naming this gap, rather than passing against a weaker one — which is what
it had silently been doing after the D2a correction removed the diagnostic it
relied on. The three reachable corners of the verdict rule are tested directly.

## Corrected scope-contract deviation

A fifth deviation was found after the first four, and unlike them it was not found
by an independent implementation or by comparing the two engines. It was found by
reading §8.1 and §8.4 against a corpus that could not exercise them.

| Deviation | Published rule | Was | Now |
|---|---|---|---|
| A finding scoped to another target or evaluation context could support a claim | §6 binds the boundary finding, every base and qualifier aggregate and every profile-gap entry to the top-level target and evaluation-context identifier; §6.2 lists exact target and context scope among the position-4 cross-field invariants; §8.1 and §8.4 independently require the same identity at admission | neither engine tested either field, so a foreign-scoped finding was admitted and could carry a claim to accept | ingress returns the Core-derived `E_PROFILE_MAPPING_INVALID` through the fixed rejection projection, and §8 admission refuses the finding as defence in depth |

Scope of the claim: this implements the **exact target and context scope** family
of §6.2 position 4. It does not implement the other five families named there,
which stay in the known-absence table above. At §8 it implements the exact-scope
predicate of §8.1 and §8.4; it is not a claim about the complete §8 surface.

Authority: `WEXP-CORE-01-VECTORS-003`, digest
`338b14cffdb846ca2aec4574ad9e52dd3615e15c8de7861d922e4323989440cd`, whose
expectations were derived from the published draft and frozen before either engine
was repaired. Both engines were repaired independently against it. Each normative
predicate above is mutation-challenged per engine, with the full logical predicate
neutralised rather than one duplicated code location.

Sets 001 and 002 are unaffected and their evidence bundle digests are unchanged at
`d673a814ca406e28d61ab0bbfeb64005f1ecadbde5ba069751b95b5fd59df4bb` and
`eb5ae9de397f7340078cb7dba20ada4041c55fb9397659ba77a26c360639007d`.

## Corrected diagnostic-projection deviation

A successor vector set, whose expectations were frozen with per-expectation
digests before either engine was run against them, surfaced a fourth deviation.
Unlike the three above it changed no verdict: the appraisal reached the right
answer about the claim and described it with the wrong diagnostic.

| Deviation | Published rule | Was | Now |
|---|---|---|---|
| Present aggregate reported as missing evidence | §8.6 "an absent aggregate triggers only its absence row; status rows require that aggregate to be present"; the matrix "is exhaustive ... No condition outside this matrix creates a Core-derived non-fatal token" | one catch-all gave `E_MISSING_REQUIRED_EVIDENCE` to any unsupported asserted claim that was not over-ceiling | the three absence rows are evaluated individually, and the catch-all survives only as the declared fallback for rows this profile cannot name |
| `qualifier_not_evaluated` never emitted from a qualifier finding | §8.6 asserted IV target-binding, semantic, or independence assessment not-evaluated; source: IV finding | the registered role was reachable only through a profile-supplied gap | the row is emitted from the IV finding, with that finding as the gap entry's source |

This row is **not** recorded as a known absence. `E_IV_NOT_EVALUATED` has a role
in the profile registry, so the row was inside the surface this document already
claimed, and the behaviour was a defect rather than a declared omission. The ten
unregistered rows are unchanged and remain known absences; in particular
`E_INDEPENDENCE_NOT_ESTABLISHED` still collapses onto the fallback, which is
tested rather than assumed.

The published Set 001 vectors are again unaffected — none of them asserts a
qualifier whose aggregate is present with an assessment that did not run — and
their evidence bundle digest is unchanged at
`d673a814ca406e28d61ab0bbfeb64005f1ecadbde5ba069751b95b5fd59df4bb`.

Both engines were corrected separately in their own idioms. No shared semantic
helper was introduced, and the independence firewall still passes.

## What engine agreement does and does not establish

    implementation diversity:              YES
    algorithmic diversity:                 YES
    semantic interpretation independence:  NOT ESTABLISHED
    independent specification derivation:  NO

The two engines were written together, from one reading of the specification.
Their agreement is evidence against some implementation-specific coding errors.
It is **not** evidence of semantic correctness, and it does not protect against a
shared interpretation defect — all three deviations above were present in both
engines identically, and their differential agreement could not detect any of
them. Only an implementation derived independently from the specification can.

The scope-contract deviation sharpens the point. Every finding in the published
corpus used one target and one evaluation context, so no input could distinguish an
implementation that enforced the scope contract from one that ignored it. Both
engines ignored it and agreed on every published vector. A differential harness
detects divergent mistakes; a dimension that never varies produces no divergence to
detect, and agreement on that dimension measured nothing.
