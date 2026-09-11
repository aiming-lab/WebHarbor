from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "sean-blackwood-45e84c50"
RESULTS = "/results?q=Family+Medicine&loc=Newark%2C+DE+19711&d=10&sortby=num_rating"
GENUINE_STEPS = [
    step("/"),
    step("/results?q=Family+Medicine&loc=Newark%2C+DE+19711"),
    step("/results?q=Family+Medicine&loc=Newark%2C+DE+19711&d=10"),
    step(RESULTS),
    step(profile(SLUG), "done"),
]
ANSWER = "NPI 1472790926; residency at Elk Neck Medical Center."


def genuine_after() -> State:
    return State()

class VerifyTask11Tests(SharedVerifierTests, VerifierTestCase):
    N = 11
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), step(RESULTS, "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_default_distance_fails(self) -> None:
        steps = [step("/"), step("/results?q=Family+Medicine&sortby=num_rating"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_results_10mi_sorted_by_ratings")

    def test_wrong_sort_fails(self) -> None:
        steps = [step("/"), step("/results?q=Family+Medicine&d=10&sortby=avg_rating"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_results_10mi_sorted_by_ratings")

    def test_top_ranked_profile_fails(self) -> None:
        steps = [step("/"), step(RESULTS), step(profile("aaron-harrington-6eddea1f"), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'NPI 1472790925; Elk Neck Medical Center', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_npi')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'NPI 1472790926; Schuylkill Medical Center', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_residency')

    def test_read_only_write_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 53)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "read_only_saved_providers_unchanged")


if __name__ == "__main__":
    unittest.main()
