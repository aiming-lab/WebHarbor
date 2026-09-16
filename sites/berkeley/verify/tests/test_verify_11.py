from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, step,
)

GENUINE_STEPS = [step("/"), step("/admissions", "done")]
ANSWER = "The freshman application deadline is November 30, and the acceptance rate is 14.4%."


class VerifyTask11Tests(SharedVerifierTests, VerifierTestCase):
    N = 11
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_shortcut_from_homepage_fails(self) -> None:
        steps = [step("/"), step("/about", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_admissions_page")

    def test_transfer_or_graduate_deadline_fails(self) -> None:
        answer = "The freshman deadline is December 1 and the acceptance rate is 11%."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_freshman_deadline")

    def test_wrong_rate_fails(self) -> None:
        answer = "The freshman deadline is November 30 and the acceptance rate is 11%."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_acceptance_rate")

    def test_negated_deadline_fails(self) -> None:
        answer = "The freshman deadline is not November 30; the acceptance rate is 14.4%."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_freshman_deadline")

    def test_alternative_phrasing_passes(self) -> None:
        answer = "Freshmen apply by Nov. 30, and Berkeley's acceptance rate is 14.4 percent."
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "program", 1)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
