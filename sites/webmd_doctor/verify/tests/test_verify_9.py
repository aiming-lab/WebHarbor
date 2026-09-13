from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "nicole-dubois-243c6e66"
RESULTS = "/results?q=Dermatologist&loc=Newark%2C+DE+19711&gender=f&newpatient=true&insuranceid=4"
GENUINE_STEPS = [
    step("/"),
    step("/results?q=Dermatologist&loc=Newark%2C+DE+19711"),
    step("/results?q=Dermatologist&loc=Newark%2C+DE+19711&gender=f"),
    step("/results?q=Dermatologist&loc=Newark%2C+DE+19711&gender=f&newpatient=true"),
    step(RESULTS),
    step(profile(SLUG), "done"),
]
ANSWER = "Tuckahoe College of Osteopathic Medicine; board certified in 2024."


def genuine_after() -> State:
    return State()

class VerifyTask9Tests(SharedVerifierTests, VerifierTestCase):
    N = 9
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), step(RESULTS, "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_filters_never_combined_fails(self) -> None:
        steps = [step("/"), step("/results?q=Dermatologist&gender=f"), step("/results?q=Dermatologist&newpatient=true"),
                 step("/results?q=Dermatologist&insuranceid=4"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_filtered_results")

    def test_insurer_missing_fails(self) -> None:
        steps = [step("/"), step("/results?q=Dermatologist&gender=f&newpatient=true"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_filtered_results")

    def test_insurer_typed_in_search_passes(self) -> None:
        steps = [step("/"), step("/results?q=Dermatologist+Blue+Cross+Blue+Shield&gender=f&newpatient=1"), step(profile(SLUG), "done")]
        self.assertPasses(self.verdict(steps, ANSWER))

    def test_wrong_candidate_profile_fails(self) -> None:
        steps = [step("/"), step(RESULTS), step(profile("celeste-bergstrom-a289f96e"), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Patuxent River College of Medicine; certified 2024', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_medical_school')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Tuckahoe College of Osteopathic Medicine; certified 2020', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_certification_year')

    def test_read_only_write_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 17)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "read_only_saved_providers_unchanged")


if __name__ == "__main__":
    unittest.main()
