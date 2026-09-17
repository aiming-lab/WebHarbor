from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    step("/register", "input", "new.candidate@test.com"),
    step("/register", "input", "BenchPass123!"),
    step("/register"),
    step("/candidate-home/saved-roles", "input", "ecom warehouse worker"),
    step("/results?q=ecom+warehouse+worker"),
    step("/jobs/CP-9046-11274"),
    step("/jobs/CP-9046-11274", "done"),
]
ANSWER = 'Registered new.candidate@test.com and saved CP-9046-11274'


def genuine_after() -> State:
    after = State()
    new_id = after.add_user("new.candidate@test.com"); after.add_saved(new_id, "CP-9046-11274")
    return after


class VerifyTask14Tests(VerifierTestCase):
    N = 14

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
        steps = only_paths(GENUINE_STEPS, "/", "/results", "/candidate-home/saved-roles", "/jobs/CP-9046-11274")
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_register_page')

    def test_state_unchanged_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State()
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'new_user_registered')

    def test_seeded_account_used_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State(); after.add_saved(1, "CP-9046-11274")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'new_user_registered')

    def test_new_user_saved_wrong_posting_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State(); uid = after.add_user("new.candidate@test.com"); after.add_saved(uid, "CP-9046-10913")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'target_saved_by_new_user')

    def test_new_user_but_seeded_account_saved_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State(); after.add_user("new.candidate@test.com"); after.add_saved(1, "CP-9046-11274")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'target_saved_by_new_user')

    def test_seeded_user_also_gained_target_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_saved(2, "CP-9046-11274")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'no_seeded_user_gained_target')

    def test_application_side_effect_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_application("CP-9046-11274", None, "new.candidate@test.com", "555-555-5555")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'applications_unchanged')

    def test_detail_page_gate_required(self) -> None:
        steps = [step("/"), step("/register", "input", "new.candidate@test.com"), step("/register"), step("/results?q=ecom", "done")]
        after = State()
        uid = after.add_user("new.candidate@test.com")
        after.add_saved(uid, "CP-9046-11274")
        self.assertFailsOn(self.verdict(steps, ANSWER, after=after), "visited_job_detail_CP-9046-11274")

    def test_multiple_new_users_fail(self) -> None:
        after = genuine_after()
        after.add_user("second@test.com")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_user_registered")

    def test_new_user_extra_save_fails(self) -> None:
        after = genuine_after()
        after.add_saved(5, "CP-9046-10913")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "target_saved_by_new_user")

    def test_existing_user_mutation_fails(self) -> None:
        after = genuine_after()
        after.set_profile(1, city="Changed")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "users_exact_delta")

    def test_registration_after_job_visit_fails_order(self) -> None:
        steps = [step("/"), step("/jobs/CP-9046-11274"), *GENUINE_STEPS[1:4]]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "workflow_in_order")


if __name__ == "__main__":
    unittest.main()
