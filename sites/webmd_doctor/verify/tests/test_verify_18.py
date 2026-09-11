from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "tariq-huang-c8120504"
TEXT = "Short wait and a clear explanation of my treatment options."
GENUINE_STEPS = [
    step("/"),
    *login_steps("david.k@test.com"),
    step("/providers/specialty/dermatology"),
    step("/providers/specialty/dermatology/maryland"),
    step("/providers/specialty/dermatology/maryland/elkton"),
    step(profile(SLUG), "click"),
    step(profile(SLUG), "input", TEXT),
    step(profile(SLUG), "click"),
    step(profile(SLUG), "done"),
]
ANSWER = "Review submitted; the profile shows it as Pending review."


def genuine_after() -> State:
    after = State()
    after.add_review(4, 18, 4, TEXT)
    return after

class VerifyTask18Tests(SharedVerifierTests, VerifierTestCase):
    N = 18
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), *login_steps("david.k@test.com"), step("/results?q=Dermatologist", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_profile_" + SLUG)

    def test_ended_elsewhere_fails(self) -> None:
        steps = GENUINE_STEPS[:-1] + [step("/account/saved", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "ended_on_profile")

    def test_state_unchanged_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=State()), "user_reviews_exact_delta")

    def test_wrong_rating_fails(self) -> None:
        after = State()
        after.add_review(4, 18, 5, TEXT)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_review_rating_is_4")

    def test_paraphrased_text_fails(self) -> None:
        after = State()
        after.add_review(4, 18, 4, "Short wait and a clear explanation of treatment options.")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_review_text_matches")

    def test_trailing_period_dropped_passes(self) -> None:
        after = State()
        after.add_review(4, 18, 4, "Short wait and a clear explanation of my treatment options")
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=after))

    def test_review_on_same_surname_doctor_fails(self) -> None:
        after = State()
        after.add_review(4, 7, 4, TEXT)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_review_is_for_target")

    def test_other_account_fails(self) -> None:
        after = State()
        after.add_review(1, 18, 4, TEXT)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_review_belongs_to_david")

    def test_two_reviews_fail(self) -> None:
        after = genuine_after()
        after.add_review(4, 18, 4, TEXT)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "user_reviews_exact_delta")

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Review submitted successfully.', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_confirms_pending')


if __name__ == "__main__":
    unittest.main()
