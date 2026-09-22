from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, State, VerifierTestCase, login_steps, step  # noqa: E402

EMAIL = "alice.j@test.com"


class VerifyTask7Tests(CommonCases, VerifierTestCase):
    N = 7
    GENUINE_STEPS = login_steps(EMAIL) + [step("/pet/luna", "click"), step("/account", "done")]
    ANSWER = "Luna was removed; Favorite pets no longer lists Luna."

    def genuine_after(self) -> State:
        after = State()
        after.remove_favorite(EMAIL, "luna")
        return after

    def test_state_mismatch_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=State()), "favorites_removed_exactly")

    def test_removed_and_added_another_fails(self):
        after = self.genuine_after()
        after.add_favorite(EMAIL, "sirius")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "favorites_added_exactly")

    def test_no_profile_visit_fails(self):
        steps = login_steps(EMAIL) + [step("/account", "done")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER, after=self.genuine_after()), "login_then_pet_then_account")

    def test_collateral_alert_fails(self):
        after = self.genuine_after()
        after.add_alert(EMAIL, "Dog", "Beagle", "10011", 25)
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "pet_alert_unchanged")


if __name__ == "__main__":
    unittest.main()
