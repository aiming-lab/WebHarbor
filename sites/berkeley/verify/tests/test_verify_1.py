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
    step("/programs?q=MBA"),
    step("/programs/business-administration-mba", "done"),
]
ANSWER = "The Haas School of Business offers the MBA; it takes 2 years."


class VerifyTask1Tests(SharedVerifierTests, VerifierTestCase):
    N = 1
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_degree_filter_also_satisfies_search_gate(self) -> None:
        steps = [step("/"), step("/programs?degree=MBA"), step("/programs/business-administration-mba", "done")]
        self.assertPasses(self.verdict(steps, ANSWER))

    def test_shortcut_without_detail_fails_on_gate(self) -> None:
        steps = [step("/"), step("/programs?q=MBA", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_program_detail_business-administration-mba")

    def test_shortcut_without_listing_fails_on_search_gate(self) -> None:
        steps = [step("/"), step("/programs/business-administration-mba", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_program_search")

    def test_wrong_school_fails(self) -> None:
        answer = "The School of Law offers the MBA; it takes 2 years."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_school")

    def test_wrong_duration_fails(self) -> None:
        answer = "The Haas School of Business offers the MBA; it takes 3 years."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_duration")

    def test_negated_school_fails(self) -> None:
        answer = "The MBA is not offered by the Haas School of Business; it takes 2 years."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_school")

    def test_alternative_phrasing_passes(self) -> None:
        answer = "Berkeley's MBA programme is run by the Haas School of Business and lasts two years."
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "program", 41)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
