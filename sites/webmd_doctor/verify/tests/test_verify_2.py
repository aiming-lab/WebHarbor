from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "ruth-thackeray-45234b97"
GENUINE_STEPS = [
    step("/"),
    step("/results?q=Family+Medicine&loc=Newark%2C+DE+19711"),
    step(profile(SLUG), "done"),
]
ANSWER = "Phone (302) 555-1542; Saturday hours 8:00 am - 1:00 pm."


def genuine_after() -> State:
    return State()

class VerifyTask2Tests(SharedVerifierTests, VerifierTestCase):
    N = 2
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), step("/results?q=Family+Medicine", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_missing_results_visit_fails(self) -> None:
        steps = [step("/"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_results_family_medicine_search")

    def test_phone_and_time_variants_pass(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, "302-555-1542, Sat 8 AM to 1 PM"))

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Phone (302) 555-4822; Saturday 8:00 am - 1:00 pm', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_primary_office_phone')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Phone (302) 555-1542; Saturday 9:00 am - 5:00 pm', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_saturday_hours')

    def test_wrong_answer_2_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Phone (302) 555-1542; closed on Saturday', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_saturday_hours')

    def test_read_only_write_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 48)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "read_only_saved_providers_unchanged")


if __name__ == "__main__":
    unittest.main()
