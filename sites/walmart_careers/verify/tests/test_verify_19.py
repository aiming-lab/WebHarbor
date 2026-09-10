from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    *login_steps("bob.c@test.com"),
    step("/careers-areas/stores-and-clubs"),
    step("/results?area=stores-and-clubs&category=digital-pickup-and-delivery"),
    step("/results?area=stores-and-clubs&category=digital-pickup-and-delivery&type=Full+time"),
    step("/jobs/CP-144-10765", "navigate"),
    step("/jobs/CP-2073-11104", "navigate"),
    step("/jobs/CP-2075-11715", "navigate"),
    step("/jobs/CP-3593-12490", "navigate"),
    step("/jobs/CP-3826-11166", "navigate"),
    step("/jobs/CP-5260-10596", "navigate"),
    step("/jobs/CP-1179-11202"),
    step("/jobs/CP-1179-11202", "done"),
]
ANSWER = 'CP-1179-11202 / 1301 SW Wanamaker Rd'


def genuine_after() -> State:
    after = State()
    after.add_saved(2, "CP-1179-11202")
    return after


class VerifyTask19Tests(VerifierTestCase):
    N = 19

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
        steps = only_paths(GENUINE_STEPS, "/", "/results", "/login", "/careers-areas/stores-and-clubs")
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_job_detail_CP-1179-11202')

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'CP-2073-11104 / 10000 Brookpark Rd', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_requisition_id')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'CP-1179-11202 / 10000 Brookpark Rd', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_street_address')

    def test_state_unchanged_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after = State()
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'target_saved_for_bob')

    def test_extra_role_saved_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_saved(2, "CP-2073-11104")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'bob_saved_roles_changed_only_by_target')

    def test_application_side_effect_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_application("CP-1179-11202", 2, "bob.c@test.com", "206-555-0178")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'applications_unchanged')

    def test_full_time_filter_missing_fails(self) -> None:
        steps = [step("/"), *login_steps("bob.c@test.com"), step("/careers-areas/stores-and-clubs"),
                 step("/results?area=stores-and-clubs&category=digital-pickup-and-delivery"), step("/jobs/CP-1179-11202", "done")]
        after = State()
        after.add_saved(2, "CP-1179-11202")
        self.assertFailsOn(self.verdict(steps, ANSWER, after=after), "visited_digital_pickup_full_time_results")

    def test_preexisting_target_noop_fails(self) -> None:
        initial = State(); initial.add_saved(2, "CP-1179-11202")
        after = State(); after.add_saved(2, "CP-1179-11202")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), "initial_target_not_saved")

    def test_other_users_saved_roles_change_fails(self) -> None:
        after = genuine_after()
        after.add_saved(1, "CP-6088-10659")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "saved_jobs_exact_delta")

    def test_area_after_results_fails_order(self) -> None:
        steps = [step("/"), *login_steps("bob.c@test.com"),
                 step("/results?category=digital-pickup-and-delivery&type=Full+time"),
                 step("/careers-areas/stores-and-clubs"),
                 *[step(f"/jobs/{job_id}") for job_id in ("CP-1179-11202", "CP-144-10765", "CP-2073-11104", "CP-2075-11715", "CP-3593-12490", "CP-3826-11166", "CP-5260-10596")]]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "workflow_in_order")


if __name__ == "__main__":
    unittest.main()
