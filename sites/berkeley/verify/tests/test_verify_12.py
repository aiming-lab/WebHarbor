from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, step,
)

GENUINE_STEPS = [step("/"), step("/programs?college=haas-business", "done")]
ANSWER = "The Haas School of Business offers a single program: the MBA in Business Administration."


class VerifyTask12Tests(SharedVerifierTests, VerifierTestCase):
    N = 12
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_shortcut_from_degree_filter_fails(self) -> None:
        steps = [step("/"), step("/programs?degree=MBA", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_haas_programme_listing")

    def test_prior_knowledge_multi_program_fails(self) -> None:
        answer = "Haas offers MBA, PhD, and MFE programs."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_programme")

    def test_extra_degree_type_near_haas_fails(self) -> None:
        answer = (
            "The Haas School of Business offers the Business Administration MBA and a PhD in "
            "Business."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_no_other_haas_degrees")

    def test_negated_programme_fails(self) -> None:
        answer = "Haas does not offer the MBA in Business Administration."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_programme")

    def test_alternative_phrasing_passes(self) -> None:
        answer = (
            "Only one degree type is available at the Haas School of Business: the MBA "
            "(Business Administration)."
        )
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_other_schools_mention_does_not_trip_the_negative(self) -> None:
        answer = (
            "The Haas School of Business offers only the MBA in Business Administration, while "
            "other schools award the PhD."
        )
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "program", 41)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
