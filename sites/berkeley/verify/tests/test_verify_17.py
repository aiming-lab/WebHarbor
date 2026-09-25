from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, step,
)

GENUINE_STEPS = [step("/"), step("/about", "done")]
ANSWER = (
    "Berkeley has 12 Nobel Laureates on the faculty, 30 varsity sports, and 105 NCAA national "
    "titles."
)


class VerifyTask17Tests(SharedVerifierTests, VerifierTestCase):
    N = 17
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_shortcut_without_about_page_fails(self) -> None:
        steps = [step("/"), step("/", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_about_page")

    def test_prizes_line_misquoted_as_faculty_count_fails(self) -> None:
        answer = "Berkeley has 107 Nobel Laureates on the faculty, 30 varsity sports, and 105 NCAA titles."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_nobel_laureates")

    def test_wrong_sports_count_fails(self) -> None:
        answer = "Berkeley has 12 Nobel Laureates on the faculty, 32 varsity sports, and 105 NCAA titles."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_varsity_sports")

    def test_negated_count_fails(self) -> None:
        answer = "Berkeley does not have 12 Nobel Laureates on the faculty."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_nobel_laureates")

    def test_distractor_claimed_as_laureates_fails(self) -> None:
        answer = (
            "Berkeley has 12 Nobel Laureates on the faculty (though the page notes 107 Nobel "
            "Laureates overall), 30 varsity sports and 105 NCAA titles."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_rejects_distractor_nobel_count")

    def test_alternative_phrasing_passes(self) -> None:
        answer = "The About page lists 12 faculty Nobel laureates, 30 varsity sports and 105 national titles."
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_alumni_prizes_line_elsewhere_is_not_a_wrong_answer(self) -> None:
        answer = (
            "Berkeley has 12 Nobel Laureates on the faculty, 30 varsity sports and 105 NCAA "
            "national titles. The page also notes that faculty, researchers and alumni have won "
            "more than 107 Nobel Prizes in total."
        )
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "research", 2)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
