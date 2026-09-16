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
    step("/programs?degree=PhD"),
    step("/programs?degree=MS", "done"),
]
ANSWER = (
    "17 programs in the catalogue require the GRE; the degree type that most commonly requires "
    "it is the PhD."
)


class VerifyTask28Tests(SharedVerifierTests, VerifierTestCase):
    N = 28
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_four_unfiltered_pages_also_satisfy_gate(self) -> None:
        steps = [step("/"), step("/programs?page=1"), step("/programs?page=2"),
                 step("/programs?page=3"), step("/programs?page=4", "done")]
        self.assertPasses(self.verdict(steps, ANSWER))

    def test_single_degree_listing_fails_gate(self) -> None:
        steps = [step("/"), step("/programs?degree=PhD", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_gre_programme_listings")

    def test_all_phd_count_fails(self) -> None:
        answer = "There are 25 programs that require the GRE, all of them PhD programs."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_gre_count")

    def test_wrong_modal_degree_fails(self) -> None:
        answer = "17 programs require the GRE, mostly master's degrees such as the MS."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_modal_degree_type")

    def test_negated_count_fails(self) -> None:
        answer = "The catalogue does not have 17 GRE-required programs."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_gre_count")

    def test_alternative_phrasing_passes(self) -> None:
        answer = "There are seventeen GRE-required programs, mostly PhD programs."
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "program", 31)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
