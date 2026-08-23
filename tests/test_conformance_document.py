"""The conformance document says what it is allowed to say, and keeps saying it.

`CONFORMANCE.md` is the only place this repository states the size of its
claimed surface. It drifted once already — describing the public corpus as
sixteen vectors after a second public set existed — so the parts that must not
move are asserted here rather than left to review.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = REPO_ROOT / "CONFORMANCE.md"

#: The declared status. Widening it is a decision, never a wording change.
DECLARED_STATUS = "wexp-ref Core-01 conformance:  PARTIAL"

#: Public Core-01 sets and their expectation counts, as wexp-vectors publishes
#: them. A count here that disagrees with that repository is a defect in one of
#: the two, and this test is where it surfaces.
PUBLIC_SETS = {"Set 001": "sixteen", "Set 002": "nine"}

#: Phrases that would assert a wider surface. The document says each of these
#: only in the negative, so the test matches the assertive form alone.
FORBIDDEN_CLAIMS = (
    "is a conformance suite",
    "full Core-01 conformance is established",
    "is a complete Core appraisal implementation",
    "conformance:  COMPLETE",
    "conformance:  FULL",
)


class ConformanceDocumentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = CONFORMANCE.read_text(encoding="utf-8")

    def test_the_declared_status_is_partial(self) -> None:
        self.assertIn(DECLARED_STATUS, self.text)

    def test_the_corpus_is_denied_as_a_conformance_suite(self) -> None:
        self.assertIn("**not a conformance suite**", self.text)

    def test_both_public_sets_are_named_with_their_counts(self) -> None:
        for name, count in PUBLIC_SETS.items():
            with self.subTest(vector_set=name):
                self.assertIn(name, self.text)
                self.assertIn(count, self.text)

    def test_no_broader_surface_is_claimed(self) -> None:
        for phrase in FORBIDDEN_CLAIMS:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, self.text)

    def test_the_prohibition_on_misdescription_survives(self) -> None:
        self.assertIn(
            "Do not describe this implementation as a conformance implementation",
            self.text,
        )

    def test_the_known_absences_stay_enumerated(self) -> None:
        section = self.text.split("## Known absences — enumerated", 1)
        self.assertEqual(len(section), 2, "the known-absences section is gone")
        body = section[1].split("None of the above", 1)[0]
        rows = re.findall(r"^\| .+ \| (?:KNOWN ABSENCE|INTENTIONALLY)", body, re.MULTILINE)
        self.assertEqual(len(rows), 6, "a known absence was added or removed")

    def test_widening_the_claim_is_still_called_out_as_untrue(self) -> None:
        self.assertIn(
            "Widening the\nclaim without implementing them would make the claim untrue.",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()
