from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, State, VerifierTestCase, login_steps, step  # noqa: E402

EMAIL = "carol.w@test.com"


class VerifyTask9Tests(CommonCases, VerifierTestCase):
    N = 9
    GENUINE_STEPS = login_steps(EMAIL) + [step("/alerts", "input", "Siamese"), step("/alerts", "input", "33130"),
                                          step("/alerts", "click"), step("/account", "done")]
    ANSWER = "Created a New Pet Alert for Siamese cats within 50 miles of 33130; it appears in the account."

    def genuine_after(self) -> State:
        after = State()
        after.add_alert(EMAIL, "Cat", "Siamese", "33130", 50)
        return after

    def test_state_mismatch_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=State()), "exactly_one_alert_added")

    def test_wrong_radius_fails(self):
        after = State()
        after.add_alert(EMAIL, "Cat", "Siamese", "33130", 25)
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "alert_values_exact")

    def test_wrong_species_fails(self):
        after = State()
        after.add_alert(EMAIL, "Dog", "Siamese", "33130", 50)
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "alert_values_exact")

    def test_duplicate_alert_fails(self):
        after = self.genuine_after()
        after.add_alert(EMAIL, "Cat", "Siamese", "33130", 50)
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "exactly_one_alert_added")

    def test_wrong_user_fails(self):
        after = State()
        after.add_alert("alice.j@test.com", "Cat", "Siamese", "33130", 50)
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "alert_belongs_to_carol")

    def test_no_alerts_page_fails(self):
        steps = login_steps(EMAIL) + [step("/account", "done")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER, after=self.genuine_after()), "login_alerts_account")


if __name__ == "__main__":
    unittest.main()
