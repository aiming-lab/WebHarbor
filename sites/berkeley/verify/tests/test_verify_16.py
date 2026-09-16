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
    step("/programs?page=3"),
    step("/programs/data-science-ms", "done"),
]
ANSWER = "Only one program offers an online option: the Data Science MS from the School of Information."


class VerifyTask16Tests(SharedVerifierTests, VerifierTestCase):
    N = 16
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_online_search_is_not_a_listing_visit(self) -> None:
        steps = [step("/"), step("/search?q=online", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_programme_listing")

    def test_shortcut_without_detail_fails(self) -> None:
        steps = [step("/"), step("/programs", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_program_detail_data-science-ms")

    def test_prior_knowledge_multiple_online_fails(self) -> None:
        answer = (
            "Several programs can be completed online, including the Computer Science MS and "
            "the Master of Engineering."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_programme")

    def test_second_online_program_fails(self) -> None:
        answer = (
            "The Data Science MS from the School of Information is online, and so is the Civil "
            "Engineering BS."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_no_other_online_programmes")

    def test_negated_programme_fails(self) -> None:
        answer = "The Data Science MS is not online."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_programme")

    def test_alternative_phrasing_passes(self) -> None:
        answer = "The Data Science MS (School of Information) is the single degree with an online option."
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "program", 26)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
