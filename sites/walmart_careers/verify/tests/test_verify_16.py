from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    step("/results"),
    step("/results?loc=Puerto+Rico&radius=25"),
    step("/results?q=cashier&shift=Weekday+Day&rate=Hourly&loc=Puerto+Rico&radius=25"),
    step("/jobs/CP-2503-11505", "navigate"),
    step("/jobs/CP-2610-11040", "navigate"),
    step("/jobs/CP-2503-10981", "navigate"),
    step("/jobs/CP-2503-10981", "done"),
]
ANSWER = 'CP-2503-10981 / 5 open positions'


def genuine_after() -> State:
    after = State()
    pass
    return after


class VerifyTask16Tests(VerifierTestCase):
    N = 16

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
        steps = [step("/"), step("/results?shift=Weekday+Day&rate=Hourly"), step("/jobs/CP-2503-10981", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_results_required_filters')

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'CP-2503-11505 / 1 open position', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_requisition_id')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'CP-2503-10981 / 1 open position', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_positions_count')

    def test_read_only_write_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_saved(2, "CP-5991-12522")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'read_only_saved_jobs_unchanged')

    def test_city_location_does_not_substitute_for_puerto_rico_scope(self) -> None:
        steps = [step("/"), step("/results?q=cashier&shift=Weekday+Day&rate=Hourly&loc=Bayamon%2C+PR&radius=60"), step("/jobs/CP-2503-10981", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_results_required_filters")

    def test_shift_filter_missing_fails(self) -> None:
        steps = [step("/"), step("/results?rate=Hourly&loc=Puerto+Rico&radius=25"), step("/jobs/CP-2503-10981", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_results_required_filters")

    def test_detail_visit_of_other_cashier_only_fails(self) -> None:
        steps = [step("/"), step("/results?q=cashier&shift=Weekday+Day&rate=Hourly&loc=Puerto+Rico&radius=25"), step("/jobs/CP-2503-11505", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_job_detail_CP-2503-10981")


if __name__ == "__main__":
    unittest.main()
