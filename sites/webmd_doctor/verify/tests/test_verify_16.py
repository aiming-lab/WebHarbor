from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "anita-castellano-14da1f29"
GENUINE_STEPS = [
    step("/"),
    *login_steps("bob.c@test.com"),
    step("/results?q=Pediatrician&loc=Newark%2C+DE+19711"),
    step(profile(SLUG), "click"),
    step(profile(SLUG)),
    step("/account/saved", "done"),
]
ANSWER = "Saved. Dr. Anita Castellano now appears under Saved Providers."


def genuine_after() -> State:
    after = State()
    after.add_saved(2, 163)
    return after

class VerifyTask16Tests(SharedVerifierTests, VerifierTestCase):
    N = 16
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), *login_steps("bob.c@test.com"), step("/results?q=Pediatrician"), step("/account/saved", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_profile_" + SLUG)

    def test_saved_page_before_profile_fails_order(self) -> None:
        steps = [step("/"), *login_steps("bob.c@test.com"), step("/account/saved"), step("/results?q=Pediatrician"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "workflow_in_order")

    def test_state_unchanged_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=State()), "saved_providers_exact_delta")

    def test_saved_under_other_account_fails(self) -> None:
        after = State()
        after.add_saved(1, 163)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_saved_row_belongs_to_bob")

    def test_saved_wrong_doctor_fails(self) -> None:
        after = State()
        after.add_saved(2, 5)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_saved_row_belongs_to_bob")

    def test_extra_save_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 5)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "saved_providers_exact_delta")

    def test_wrong_account_fails(self) -> None:
        steps = [step("/"), *login_steps("alice.j@test.com"), *GENUINE_STEPS[4:]]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "entered_expected_account_email")

    def test_collateral_write_fails(self) -> None:
        after = genuine_after()
        after.add_review(2, 163, 5, "Collateral review text that is long enough to pass.")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "user_reviews_unchanged")

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Done.', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_confirms_saved')


if __name__ == "__main__":
    unittest.main()
