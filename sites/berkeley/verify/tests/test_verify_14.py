from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, step,
)

GENUINE_STEPS = [step("/"), step("/academics", "done")]
ANSWER = (
    "The College of Engineering enrolls 4,500 undergraduates and 3,200 graduate students; the "
    "dean is Dean Tsu-Jae King Liu."
)


class VerifyTask14Tests(SharedVerifierTests, VerifierTestCase):
    N = 14
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_shortcut_from_about_page_fails(self) -> None:
        steps = [step("/"), step("/about", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_academics_page")

    def test_university_wide_totals_fail(self) -> None:
        answer = (
            "The College of Engineering enrolls 31,800 undergraduates and 12,000 graduate "
            "students; the dean is Dean Tsu-Jae King Liu."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_undergrad_count")

    def test_wrong_dean_fails(self) -> None:
        answer = "The College of Engineering enrolls 4,500 undergraduates and 3,200 graduate students."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_dean")

    def test_negated_dean_fails(self) -> None:
        answer = (
            "The College of Engineering enrolls 4,500 undergraduates and 3,200 graduate "
            "students; the dean is not Tsu-Jae King Liu."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_dean")

    def test_alternative_phrasing_passes(self) -> None:
        answer = (
            "Engineering has 4500 undergrads and 3200 grad students, led by Dean Tsu-Jae King Liu."
        )
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "program", 1)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
