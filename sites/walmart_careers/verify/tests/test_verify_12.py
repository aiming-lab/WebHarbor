from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    *login_steps("bob.c@test.com"),
    step("/account"),
    step("/candidate-home/saved-roles"),
    step("/candidate-home/saved-roles", "done"),
]
ANSWER = 'Removed the Asset Protection Associate role at Neighborhood Market #5991'


def genuine_after() -> State:
    after = State()
    after.remove_saved(2, "CP-5991-11940")
    return after


class VerifyTask12Tests(VerifierTestCase):
    N = 12

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
        steps = [step("/"), *login_steps("bob.c@test.com"), step("/account", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_saved_roles_page')

    def test_state_unchanged_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State()
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'target_removed_for_bob')

    def test_wrong_role_removed_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State(); after.remove_saved(2, "CP-6038-12357")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'target_removed_for_bob')

    def test_two_roles_removed_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.remove_saved(2, "CP-6038-12357")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'bob_saved_roles_changed_only_by_target')

    def test_other_users_roles_touched_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.remove_saved(1, "CP-5991-12522")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), "saved_jobs_exact_delta")

    def test_application_side_effect_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_application("CP-5991-11940", 2, "bob.c@test.com", "206-555-0178")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'applications_unchanged')


if __name__ == "__main__":
    unittest.main()
