from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, State, VerifierTestCase, login_steps, step  # noqa: E402

EMAIL = "david.b@test.com"


class VerifyTask15Tests(CommonCases, VerifierTestCase):
    N = 15
    GENUINE_STEPS = login_steps(EMAIL) + [step("/search?location=Austin%2C+TX&species=Dog"), step("/pet/archie", "click"),
                                          step("/search?location=Austin%2C+TX&species=Dog"), step("/pet/ruby", "click"), step("/account", "done")]
    ANSWER = "Archie and Ruby are both listed under Favorite pets."

    def genuine_after(self) -> State:
        after = State()
        after.add_favorite(EMAIL, "archie")
        after.add_favorite(EMAIL, "ruby")
        return after

    def test_state_mismatch_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=State()), "favorites_added_exactly")

    def test_only_one_favorited_fails(self):
        after = State()
        after.add_favorite(EMAIL, "archie")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "favorites_added_exactly")

    def test_extra_favorite_fails(self):
        after = self.genuine_after()
        after.add_favorite(EMAIL, "olive")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "favorites_added_exactly")

    def test_account_before_second_pet_fails(self):
        steps = login_steps(EMAIL) + [step("/pet/archie", "click"), step("/account"), step("/pet/ruby", "done")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER, after=self.genuine_after()), "login_then_ruby_then_account")


if __name__ == "__main__":
    unittest.main()
