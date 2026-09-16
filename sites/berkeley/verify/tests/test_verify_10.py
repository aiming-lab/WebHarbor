from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, step,
)

GENUINE_STEPS = [step("/"), step("/research/bair", "done")]
ANSWER = "BAIR was founded in 2013 and is directed by Prof. Pieter Abbeel."


class VerifyTask10Tests(SharedVerifierTests, VerifierTestCase):
    N = 10
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_shortcut_from_listing_fails(self) -> None:
        steps = [step("/"), step("/research", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_research_detail_bair")

    def test_real_world_founding_year_fails(self) -> None:
        answer = "BAIR was founded in 2017 and is directed by Prof. Pieter Abbeel."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_founded_year")

    def test_wrong_director_fails(self) -> None:
        answer = "BAIR was founded in 2013 and is directed by Prof. David Culler."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_director")

    def test_negated_year_fails(self) -> None:
        answer = "BAIR is directed by Prof. Pieter Abbeel, but it was not founded in 2013."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_founded_year")

    def test_fully_negated_answer_fails_on_first_check(self) -> None:
        answer = "BAIR was not founded in 2013."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_director")

    def test_alternative_phrasing_passes(self) -> None:
        answer = (
            "The Berkeley Artificial Intelligence Research Lab's director is Pieter Abbeel, and "
            "it was established in 2013."
        )
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "research", 1)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
