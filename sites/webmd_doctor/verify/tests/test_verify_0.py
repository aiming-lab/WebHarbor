from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "jonah-dimitriou-c4ce067c"
GENUINE_STEPS = [
    step("/"),
    step("/", "input", "Dermatologist"),
    step("/results?q=Dermatologist&loc=Newark%2C+DE+19711"),
    step(profile(SLUG), "done"),
]
ANSWER = "Dr. Dimitriou graduated from Chesapeake Bay School of Medicine in 2004."


def genuine_after() -> State:
    return State()

class VerifyTask0Tests(SharedVerifierTests, VerifierTestCase):
    N = 0
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), step("/results?q=Dermatologist", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_missing_results_visit_fails(self) -> None:
        steps = [step("/"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_results_dermatologist_search")

    def test_other_city_search_fails_gate(self) -> None:
        steps = [step("/"), step("/results?q=Dermatologist&loc=Wilmington%2C+DE"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_results_dermatologist_search")

    def test_same_surname_profile_fails(self) -> None:
        steps = [step("/"), step("/results?q=Dermatologists"), step(profile("timothy-dimitriou-00000000"), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_sids_and_tab_alias_pass(self) -> None:
        steps = [step("/"), step("/results?sids=1"), step("/doctor/" + SLUG + "-locations", "done")]
        self.assertPasses(self.verdict(steps, "Chesapeake Bay School Of Medicine, class of 2004"))

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Dr. Dimitriou graduated from Great Falls University Hospital in 2004.', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_medical_school')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Chesapeake Bay School of Medicine, 2008', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_graduation_year')

    def test_read_only_write_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 1)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "read_only_saved_providers_unchanged")


    def test_profile_before_results_fails(self) -> None:
        steps = [step("/"), step(profile(SLUG)), step("/results?q=Dermatologist&loc=Newark%2C+DE+19711", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "results_precede_profile")


if __name__ == "__main__":
    unittest.main()
