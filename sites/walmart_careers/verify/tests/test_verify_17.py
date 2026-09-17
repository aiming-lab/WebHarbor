from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    *login_steps("alice.j@test.com"),
    step("/candidate-home/saved-roles"),
    step("/jobs/CP-9046-10913", "navigate"),
    step("/jobs/CP-2503-11505"),
    step("/jobs/CP-2503-11505/apply"),
    step("/jobs/CP-2503-11505/apply/confirm"),
    step("/jobs/CP-2503-11505/apply/submitted", "done"),
]
ANSWER = 'Shift may start between 6:00am - 11:00am / confirmation WMC-000005'


def genuine_after() -> State:
    after = State()
    after.add_application("CP-2503-11505", 1, "alice.j@test.com", "479-555-0134")
    return after


class VerifyTask17Tests(VerifierTestCase):
    N = 17

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
        steps = only_paths(GENUINE_STEPS, "/", "/results", "/login")
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_saved_roles_page')

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Shift may start between 12:00pm - 5:00pm / confirmation WMC-000005', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_shift_window')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Shift may start between 6:00am - 11:00am / confirmation WMC-000009', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_matching_confirmation_number')

    def test_state_unchanged_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State()
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'exactly_one_new_application')

    def test_applied_to_full_time_role_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State(); after.add_application("CP-9046-10913", 1, "alice.j@test.com", "479-555-0134")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'new_application_is_for_part_time_saved_role')

    def test_applied_with_other_email_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State(); after.add_application("CP-2503-11505", 1, "someone@else.com", "479-555-0134")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'new_application_belongs_to_alice')

    def test_preexisting_target_application_fails(self) -> None:
        initial = State(); initial.add_application("CP-2503-11505", 1, "alice.j@test.com", "479-555-0134")
        after = State(); after.add_application("CP-2503-11505", 1, "alice.j@test.com", "479-555-0134")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), "initial_has_no_alice_application_for_target")

    def test_saved_role_mutation_fails(self) -> None:
        after = genuine_after()
        after.remove_saved(1, "CP-9046-10913")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "saved_jobs_unchanged")

    def test_missing_confirm_page_fails(self) -> None:
        steps = [item for item in GENUINE_STEPS if not item["url"].endswith("/apply/confirm")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_apply_confirm_page")


if __name__ == "__main__":
    unittest.main()
