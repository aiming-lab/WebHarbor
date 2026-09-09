from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    *login_steps("david.k@test.com"),
    step("/account"),
    step("/account/edit", "input", "Rogers"),
    step("/account/edit", "input", "AR"),
    step("/account/edit"),
    step("/account"),
    step("/account"),
    step("/candidate-home/applications", "done"),
]
ANSWER = 'Profile updated to Rogers, AR / existing application WMC-000004'


def genuine_after() -> State:
    after = State()
    after.set_profile(4, city="Rogers", state="AR")
    return after


class VerifyTask15Tests(VerifierTestCase):
    N = 15

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after()))

    def test_run_dir_snapshots_are_discovered(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after(), snapshots_in_run_dir=True)
        self.assertPasses(verdict)

    def test_noop_run_fails_on_empty_answer(self) -> None:
        self.assertFailsOn(self.verdict([step("/")], ""), "final_answer_nonempty")

    def test_other_task_trajectory_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after(), task_id="Walmart Careers--99")
        self.assertFailsOn(verdict, "trajectory_task_matches")

    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), *login_steps("david.k@test.com"), step("/account/edit", "input", "Rogers"), step("/account/edit", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_applications_page')

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Profile updated / WMC-000001', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_existing_confirmation_number')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Profile updated / WMC-000005', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_existing_confirmation_number')

    def test_state_unchanged_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State()
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'profile_city_and_state_updated')

    def test_only_city_changed_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State(); after.set_profile(4, city="Rogers")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'profile_city_and_state_updated')

    def test_new_application_side_effect_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_application("R-2434655", 4, "david.k@test.com", "214-555-0166")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'applications_unchanged')

    def test_other_user_edited_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.set_profile(1, city="Rogers", state="AR")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'other_users_unchanged')

    def test_lowercase_state_and_city_accepted(self) -> None:
        after = State()
        after.set_profile(4, city="rogers", state="AR")
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=after))

    def test_preexisting_requested_profile_noop_fails(self) -> None:
        initial = State(); initial.set_profile(4, city="Rogers", state="AR")
        after = State(); after.set_profile(4, city="Rogers", state="AR")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), "initial_profile_requires_update")

    def test_other_profile_field_change_fails(self) -> None:
        after = State()
        after.set_profile(4, city="Rogers", state="AR", phone="999-555-1212")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "profile_exact_delta")

    def test_applications_before_edit_fails_order(self) -> None:
        steps = [step("/"), *login_steps("david.k@test.com"), step("/candidate-home/applications"),
                 step("/account/edit", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "workflow_in_order")


if __name__ == "__main__":
    unittest.main()
