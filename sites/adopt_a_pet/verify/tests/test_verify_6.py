from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, State, VerifierTestCase, login_steps, step  # noqa: E402

EMAIL = "alice.j@test.com"


class VerifyTask6Tests(CommonCases, VerifierTestCase):
    N = 6
    GENUINE_STEPS = login_steps(EMAIL) + [step("/search?location=Scottsdale%2C+AZ&species=Dog"), step("/pet/sirius", "click"), step("/account", "done")]
    ANSWER = "Sirius was added to favorites; Favorite pets now lists Sirius and Luna."

    def genuine_after(self) -> State:
        after = State()
        after.add_favorite(EMAIL, "sirius")
        return after

    def test_state_mismatch_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=State()), "favorites_added_exactly")

    def test_collateral_favorite_fails(self):
        after = self.genuine_after()
        after.add_favorite(EMAIL, "waymo")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "favorites_added_exactly")

    def test_wrong_user_favorited_fails(self):
        after = State()
        after.add_favorite("bob.smith@test.com", "sirius")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "favorites_added_exactly")

    def test_luna_removed_fails(self):
        after = self.genuine_after()
        after.remove_favorite(EMAIL, "luna")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "favorites_removed_exactly")

    def test_no_account_visit_after_action_fails(self):
        steps = login_steps(EMAIL) + [step("/pet/sirius", "done")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER, after=self.genuine_after()), "login_then_pet_then_account")

    def test_wrong_login_email_fails(self):
        steps = login_steps("bob.smith@test.com") + [step("/pet/sirius", "click"), step("/account", "done")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER, after=self.genuine_after()), "entered_expected_account_email")

    def test_answer_missing_luna_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Added Sirius to favorites.", after=self.genuine_after()), "answer_confirms_both_pets")


if __name__ == "__main__":
    unittest.main()
