from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    *login_steps("alice.j@test.com"),
    step("/", "input", "yard driver"),
    step("/results?q=yard+driver"),
    step("/jobs/CP-6088-10659"),
    step("/jobs/CP-6088-10659", "navigate"),
    step("/candidate-home/saved-roles", "done"),
]
ANSWER = 'Saved the Yard Driver-Off Property posting in Williamsburg, VA'


def genuine_after() -> State:
    after = State()
    after.add_saved(1, "CP-6088-10659")
    return after


class VerifyTask11Tests(VerifierTestCase):
    N = 11

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
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_job_detail_CP-6088-10659')

    def test_state_unchanged_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State()
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'target_saved_for_alice')

    def test_extra_role_saved_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_saved(1, "CP-6088-11595")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'alice_saved_roles_changed_only_by_target')

    def test_wrong_role_saved_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State(); after.add_saved(1, "CP-6088-11595")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'target_saved_for_alice')

    def test_saved_by_other_account_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State(); after.add_saved(2, "CP-6088-10659")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'target_saved_for_alice')

    def test_application_side_effect_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_application("CP-6088-10659", 1, "alice.j@test.com", "479-555-0134")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'applications_unchanged')

    def test_already_saved_precondition_fails(self) -> None:
        initial = State()
        after = genuine_after()
        initial.add_saved(1, "CP-6088-10659")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'initial_target_not_saved')

    def test_wrong_account_login_fails(self) -> None:
        steps = [step("/"), *login_steps("bob.c@test.com"), step("/results?q=yard+driver"), step("/jobs/CP-6088-10659", "done")]
        after = State()
        after.add_saved(1, "CP-6088-10659")
        self.assertFailsOn(self.verdict(steps, ANSWER, after=after), "entered_expected_account_email")


if __name__ == "__main__":
    unittest.main()
