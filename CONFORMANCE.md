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
