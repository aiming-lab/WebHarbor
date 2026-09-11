from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "joseph-iyer-29b88273"
CITY = "/providers/specialty/cardiovascular-disease/pennsylvania/west-chester"
GENUINE_STEPS = [
    step("/"),
    step("/providers/specialty/cardiovascular-disease"),
    step("/providers/specialty/cardiovascular-disease/pennsylvania"),
    step(CITY),
    step(CITY + "?minrating=4"),
    step(profile(SLUG), "done"),
]
ANSWER = "Fellowship at Allegheny Ridge Medical Center, completed in 1987."


def genuine_after() -> State:
    return State()

class VerifyTask12Tests(SharedVerifierTests, VerifierTestCase):
    N = 12
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), step("/results?q=Cardiologist&loc=West+Chester%2C+PA&minrating=4"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_specialty_landing_page")

    def test_city_page_without_rating_filter_fails(self) -> None:
        steps = [step("/"), step("/providers/specialty/cardiovascular-disease"), step("/providers/specialty/cardiovascular-disease/pennsylvania"),
                 step(CITY), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_city_page_rated_4_up")

    def test_gender_filter_too_passes(self) -> None:
        steps = GENUINE_STEPS[:-1] + [step(CITY + "?minrating=4&gender=m"), step(profile(SLUG), "done")]
        self.assertPasses(self.verdict(steps, ANSWER))

    def test_wrong_male_profile_fails(self) -> None:
        steps = GENUINE_STEPS[:-1] + [step(profile("jamal-sterling-d2de7bf5"), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Fellowship at Delmarva Bay Medical Center, 1987', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_fellowship')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Fellowship at Allegheny Ridge Medical Center, 1984', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_fellowship_year')

    def test_read_only_write_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 39)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "read_only_saved_providers_unchanged")


    def test_filtered_city_page_after_profile_fails(self) -> None:
        steps = [step("/"), step("/providers/specialty/cardiovascular-disease"), step("/providers/specialty/cardiovascular-disease/pennsylvania"),
                 step(CITY), step(profile(SLUG), "click"), step(CITY + "?minrating=4", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "filtered_city_precedes_profile")


if __name__ == "__main__":
    unittest.main()
