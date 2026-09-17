from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, step,
)

GENUINE_STEPS = [
    step("/"),
    step("/programs?degree=JD"),
    step("/programs/juris-doctor-jd", "done"),
]
ANSWER = (
    "The JD at Berkeley takes 3 years, has a February 1 deadline, and is offered by the School "
    "of Law."
)


class VerifyTask20Tests(SharedVerifierTests, VerifierTestCase):
    N = 20
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_shortcut_without_detail_fails(self) -> None:
        steps = [step("/"), step("/programs?degree=JD", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_program_detail_juris-doctor-jd")

    def test_mba_values_fail(self) -> None:
        answer = "The JD takes 2 years, has a January 5 deadline, and is offered by the Haas School of Business."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_duration")

    def test_optometry_deadline_is_not_enough(self) -> None:
        answer = "The JD takes 3 years, has a February 1 deadline, and is offered by the School of Optometry."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_school")

    def test_negated_duration_fails(self) -> None:
        answer = (
            "The JD does not take 3 years; it has a February 1 deadline and is offered by the "
            "School of Law."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_duration")

    def test_alternative_phrasing_passes(self) -> None:
        answer = (
            "Berkeley Law's Juris Doctor is a 3-year degree; applications are due by Feb 1 and "
            "the school is the School of Law."
        )
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "program", 42)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
