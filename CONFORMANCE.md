# Conformance status

    wexp-ref Core-01 conformance:  PARTIAL

This is a deliberate, enumerated partial surface, not a claim of complete Core
appraisal. Do not describe this implementation as a conformance implementation,
as full Core-01 conformance, or as a complete Core appraisal implementation.

The public sixteen-vector corpus is **not a conformance suite**. Passing it means
sixteen transcribed expectations were met.

## Implemented

- §4.4 typed claims and the admissible domain, including multi-qualifier states
- §4.5 structural product order, and its exclusion as an exact-support predicate
- §6.2 ingress ordering positions 1–4 and the fixed rejection projection
- §8.1 supported-claim construction over the subsets of Q(b), with limitation
  carry-through
- §8.2 counter-evidence blocking, scoped to entries whose affected claims include
  the asserted claim or all-admissible-claims
- §8.4 the accept / downgrade / reject verdict conditions as published
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

The published sixteen vectors are unaffected by all three corrections: none of
them carries two qualifiers on one base, an unrelated over-ceiling finding, or an
accept with a non-empty diagnostic set. Their evidence bundle digest is unchanged.

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

The published sixteen are again unaffected — none of them asserts a qualifier
whose aggregate is present with an assessment that did not run — and their
evidence bundle digest is unchanged at
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
