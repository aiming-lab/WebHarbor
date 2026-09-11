from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "fatima-jensen-e5a26d53"
GENUINE_STEPS = [
    step("/"),
    step("/providers/specialty/psychiatry"),
    step("/providers/specialty/psychiatry/pennsylvania"),
    step("/providers/specialty/psychiatry/pennsylvania/media"),
    step(profile(SLUG)),
    step(profile(SLUG) + "?rpage=2", "done"),
]
ANSWER = "The oldest review is dated November 2, 2022 and gave 4 stars."


def genuine_after() -> State:
    return State()

class VerifyTask6Tests(SharedVerifierTests, VerifierTestCase):
    N = 6
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), step("/providers/specialty/psychiatry/pennsylvania/media", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_first_review_page_only_fails(self) -> None:
        steps = [step("/"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_reviews_page_2")

    def test_date_and_rating_variants_pass(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, "Oldest: Nov 2, 2022, rated 4/5"))
        self.assertPasses(self.verdict(GENUINE_STEPS, "2022-11-02 - four stars"))

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'The oldest review is dated February 16, 2023 with 4 stars.', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_oldest_review_date')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'November 2, 2022 - 5 stars', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_oldest_review_rating')

    def test_wrong_answer_2_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'November 2, 2022; the rating is not 4 stars', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_oldest_review_rating')

    def test_read_only_write_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 138)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "read_only_saved_providers_unchanged")


    def test_date_and_rating_from_different_reviews_fail(self) -> None:
        bad = "The oldest review was November 2, 2022 and had 5 stars. Another review had 4 stars."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, bad), "answer_pairs_oldest_date_and_rating")


if __name__ == "__main__":
    unittest.main()
