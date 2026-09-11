from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "adrian-navarro-b338ac81"
GENUINE_STEPS = [
    step("/"),
    *login_steps("alice.j@test.com"),
    step("/account/saved"),
    step(profile(SLUG)),
    step("/account/saved", "click"),
    step("/account/saved", "done"),
]
ANSWER = "Residency: Piedmont Atlantic Hospital. Removed the provider from Saved Providers."


def genuine_after() -> State:
    after = State()
    after.remove_saved(1, 5)
    return after

class VerifyTask8Tests(SharedVerifierTests, VerifierTestCase):
    N = 8
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), *login_steps("alice.j@test.com"), step("/results?q=Dermatologist"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_saved_providers_page")

    def test_saved_page_after_profile_only_fails_order(self) -> None:
        steps = [step("/"), *login_steps("alice.j@test.com"), step(profile(SLUG)), step("/account/saved", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "workflow_in_order")

    def test_wrong_account_fails(self) -> None:
        steps = [step("/"), *login_steps("bob.c@test.com"), step("/account/saved"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "entered_expected_account_email")

    def test_state_unchanged_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=State()), "removed_target_only")

    def test_wrong_row_removed_fails(self) -> None:
        after = State()
        after.remove_saved(1, 47)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "removed_target_only")

    def test_two_rows_removed_fails(self) -> None:
        after = genuine_after()
        after.remove_saved(1, 47)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "removed_target_only")

    def test_collateral_write_fails(self) -> None:
        after = genuine_after()
        after.add_review(1, 5, 5, "Collateral review text that is long enough to pass.")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "user_reviews_unchanged")

    def test_removed_via_profile_toggle_passes(self) -> None:
        steps = [step("/"), *login_steps("alice.j@test.com"), step("/account/saved"), step(profile(SLUG), "click"), step(profile(SLUG), "done")]
        self.assertPasses(self.verdict(steps, ANSWER, after=genuine_after()))

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Residency: Rappahannock University Hospital. Removed.', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_residency')


if __name__ == "__main__":
    unittest.main()
