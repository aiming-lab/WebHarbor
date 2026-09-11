from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "monica-carrington-62f5d8a2"
EMAIL = "new.user@example.com"
GENUINE_STEPS = [
    step("/"),
    *signup_steps(EMAIL),
    step("/results?q=Neurologist&loc=Newark%2C+DE+19711"),
    step("/results?q=Neurologist&loc=Newark%2C+DE+19711&isvirtualvisit=true"),
    step(profile(SLUG), "click"),
    step(profile(SLUG), "done"),
]
ANSWER = "Registered and saved the provider. NPI: 1074536057"


def genuine_after() -> State:
    after = State()
    user_id = after.add_user(EMAIL)
    after.add_saved(user_id, 68)
    return after

class VerifyTask19Tests(SharedVerifierTests, VerifierTestCase):
    N = 19
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), *login_steps("alice.j@test.com"), step("/results?q=Neurologist&isvirtualvisit=true"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_signup_page")

    def test_virtual_filter_missing_fails(self) -> None:
        steps = [step("/"), *signup_steps(EMAIL), step("/results?q=Neurologist"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_virtual_neurologist_results")

    def test_virtual_typed_in_search_passes(self) -> None:
        steps = [step("/"), *signup_steps(EMAIL), step("/results?q=Neurologist+virtual+visit"), step(profile(SLUG), "done")]
        self.assertPasses(self.verdict(steps, ANSWER, after=genuine_after()))

    def test_no_registration_fails(self) -> None:
        after = State()
        after.add_saved(1, 68)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "users_exact_delta")

    def test_registered_with_other_email_fails(self) -> None:
        after = State()
        user_id = after.add_user("someone@else.com")
        after.add_saved(user_id, 68)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_user_email_matches_signup_input")

    def test_registered_but_not_saved_fails(self) -> None:
        after = State()
        after.add_user(EMAIL)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "saved_providers_exact_delta")

    def test_saved_under_seed_account_fails(self) -> None:
        after = State()
        after.add_user(EMAIL)
        after.add_saved(1, 68)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_saved_row_belongs_to_new_user")

    def test_saved_wrong_doctor_fails(self) -> None:
        after = State()
        user_id = after.add_user(EMAIL)
        after.add_saved(user_id, 61)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_saved_row_is_for_target")

    def test_two_accounts_fail(self) -> None:
        after = genuine_after()
        after.add_user("second@example.com")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "users_exact_delta")

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Registered and saved the provider. NPI: 1279956603', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_npi')


    def test_qualifying_results_after_profile_fails(self) -> None:
        steps = [step("/"), *signup_steps(EMAIL), step("/results"),
                 step(profile(SLUG), "click"), step(profile(SLUG), "click"),
                 step("/results?q=Neurologist&loc=Newark%2C+DE+19711&isvirtualvisit=true", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "qualifying_results_precede_profile")


if __name__ == "__main__":
    unittest.main()
