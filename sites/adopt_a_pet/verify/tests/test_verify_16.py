from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, State, VerifierTestCase, register_steps, step  # noqa: E402

EMAIL, NAME, PASSWORD = "jamie.lee@example.test", "Jamie Lee", "PetFriend123!"


class VerifyTask16Tests(CommonCases, VerifierTestCase):
    N = 16
    GENUINE_STEPS = register_steps(NAME, EMAIL, PASSWORD) + [step("/search?location=Miami%2C+FL&species=Cat"), step("/pet/olive", "click"), step("/account", "done")]
    ANSWER = "Account created for Jamie Lee; Olive now appears under Favorite pets."

    def genuine_after(self) -> State:
        after = State()
        after.add_user(EMAIL, NAME, PASSWORD)
        after.add_favorite(EMAIL, "olive")
        return after

    def test_state_mismatch_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=State()), "exactly_one_user_added")

    def test_user_without_favorite_fails(self):
        after = State()
        after.add_user(EMAIL, NAME, PASSWORD)
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "favorites_added_exactly")

    def test_wrong_password_fails(self):
        after = State()
        after.add_user(EMAIL, NAME, "SomethingElse1!")
        after.add_favorite(EMAIL, "olive")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "new_user_password_verifies")

    def test_wrong_name_fails(self):
        after = State()
        after.add_user(EMAIL, "Jamie", PASSWORD)
        after.add_favorite(EMAIL, "olive")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "new_user_has_expected_email_and_name")

    def test_wrong_email_typed_fails(self):
        steps = register_steps(NAME, "jamie@example.test", PASSWORD) + [step("/pet/olive", "click"), step("/account", "done")]
        after = State()
        after.add_user("jamie@example.test", NAME, PASSWORD)
        after.add_favorite("jamie@example.test", "olive")
        self.assertFailsOn(self.verdict(steps, self.ANSWER, after=after), "registered_through_form")

    def test_favorite_by_existing_user_fails(self):
        after = State()
        after.add_user(EMAIL, NAME, PASSWORD)
        after.add_favorite("alice.j@test.com", "olive")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "favorites_added_exactly")


if __name__ == "__main__":
    unittest.main()
