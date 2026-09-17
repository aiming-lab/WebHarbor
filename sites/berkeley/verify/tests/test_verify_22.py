from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, step,
)

GENUINE_STEPS = [step("/"), step("/departments", "done")]
ANSWER = (
    "The College of Letters and Science lists 8 departments: Economics, English, History, "
    "Mathematics, Physics and Political Science."
)


class VerifyTask22Tests(SharedVerifierTests, VerifierTestCase):
    N = 22
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_shortcut_from_college_filter_fails(self) -> None:
        steps = [step("/"), step("/programs?college=letters-and-science", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_departments_page")

    def test_sitewide_department_total_fails(self) -> None:
        answer = "The College of Letters and Science has 30 departments."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_department_count")

    def test_count_without_names_fails(self) -> None:
        answer = "The College of Letters and Science lists 8 departments."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_names_ls_departments")

    def test_count_of_wrong_college_fails(self) -> None:
        answer = "The College of Engineering has 7 departments: Economics and English."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_department_count")

    def test_negated_count_fails(self) -> None:
        answer = "The College of Letters and Science does not have 8 departments."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_department_count")

    def test_alternative_phrasing_passes(self) -> None:
        answer = (
            "There are eight departments under the College of Letters and Science (Economics, "
            "English, History and Mathematics)."
        )
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "program", 8)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
