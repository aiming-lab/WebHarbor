from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "veronica-nwachukwu-71051d38"
RESULTS = "/results?q=Psychiatrist&loc=Newark%2C+DE+19711&medicaid=true&minrating=4"
GENUINE_STEPS = [
    step("/"),
    step("/results?q=Psychiatrist&loc=Newark%2C+DE+19711"),
    step("/results?q=Psychiatrist&loc=Newark%2C+DE+19711&medicaid=true"),
    step(RESULTS),
    step(profile(SLUG), "done"),
]
ANSWER = "Average wait time 25 minutes; residency at Rappahannock University Hospital."


def genuine_after() -> State:
    return State()

class VerifyTask10Tests(SharedVerifierTests, VerifierTestCase):
    N = 10
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), step(RESULTS, "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_rating_filter_missing_fails(self) -> None:
        steps = [step("/"), step("/results?q=Psychiatrist&medicaid=true"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_medicaid_rated_results")

    def test_medicaid_filter_missing_fails(self) -> None:
        steps = [step("/"), step("/results?q=Psychiatrist&minrating=4"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_medicaid_rated_results")

    def test_wrong_candidate_profile_fails(self) -> None:
        steps = [step("/"), step(RESULTS), step(profile("luis-corwin-92a05b04"), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Average wait time 45 minutes; residency Rappahannock University Hospital', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_wait_minutes')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Average wait time 25 minutes; residency Tuckahoe College of Osteopathic Medicine', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_residency')

    def test_read_only_write_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 129)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "read_only_saved_providers_unchanged")


    def test_insurer_filter_route_no_longer_passes(self) -> None:
        # insuranceid=7 (insurer acceptance) is a different predicate than the
        # location-Medicaid facet used by the ground-truth derivation.
        steps = [step("/"), step("/results?q=Psychiatrist&loc=Newark%2C+DE+19711&insuranceid=7&minrating=4"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_medicaid_rated_results")

    def test_results_after_profile_fails(self) -> None:
        steps = [step("/"), step(profile(SLUG)), step(RESULTS, "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "filtered_results_precede_profile")


if __name__ == "__main__":
    unittest.main()
