from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, State, VerifierTestCase, login_steps, step  # noqa: E402

EMAIL = "bob.smith@test.com"
EXPERIENCE = "I have cared for two family dogs for eight years."


class VerifyTask8Tests(CommonCases, VerifierTestCase):
    N = 8
    GENUINE_STEPS = login_steps(EMAIL) + [step("/search?location=Seattle%2C+WA&species=Dog"), step("/pet/daisy"),
                                          step("/apply/daisy", "input", "206-555-0199"), step("/apply/daisy", "input", EXPERIENCE),
                                          step("/apply/daisy", "click"), step("/account", "done")]
    ANSWER = "The adoption inquiry for Daisy was sent and shows as Submitted in the account."

    def genuine_after(self) -> State:
        after = State()
        after.add_application(EMAIL, "daisy", "Rent with permission", EXPERIENCE, "206-555-0199")
        return after

    def test_state_mismatch_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=State()), "exactly_one_application_added")

    def test_wrong_housing_fails(self):
        after = State()
        after.add_application(EMAIL, "daisy", "Own home", EXPERIENCE, "206-555-0199")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "application_housing_exact")

    def test_wrong_phone_fails(self):
        after = State()
        after.add_application(EMAIL, "daisy", "Rent with permission", EXPERIENCE, "206-555-0119")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "application_phone_exact")

    def test_wrong_experience_fails(self):
        after = State()
        after.add_application(EMAIL, "daisy", "Rent with permission", "I have cared for dogs for years.", "206-555-0199")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "application_experience_exact")

    def test_trailing_period_tolerated(self):
        after = State()
        after.add_application(EMAIL, "daisy", "Rent with permission", EXPERIENCE.rstrip("."), "2065550199")
        self.assertPasses(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after))

    def test_wrong_pet_fails(self):
        after = State()
        after.add_application(EMAIL, "pepper", "Rent with permission", EXPERIENCE, "206-555-0199")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "application_belongs_to_bob_for_daisy")

    def test_no_apply_page_fails(self):
        steps = login_steps(EMAIL) + [step("/pet/daisy"), step("/account", "done")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER, after=self.genuine_after()), "login_pet_apply_account")

    def test_answer_without_status_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Done.", after=self.genuine_after()), "answer_confirms_submitted_for_daisy")


if __name__ == "__main__":
    unittest.main()
