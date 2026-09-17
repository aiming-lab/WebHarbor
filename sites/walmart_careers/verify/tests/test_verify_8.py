from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    step("/", "input", "auto care center technician"),
    step("/results?q=auto+care+center+technician"),
    step("/jobs/CP-1230-11592"),
    step("/results?q=auto+care+center+technician"),
    step("/jobs/CP-954-10637", "done"),
]
ANSWER = 'Store #1230 with 5 open positions'


def genuine_after() -> State:
    after = State()
    pass
    return after


class VerifyTask8Tests(VerifierTestCase):
    N = 8

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
        steps = [step("/"), step("/results?q=auto+care+center+technician"), step("/jobs/CP-1230-11592", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_job_detail_CP-954-10637')

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Store #954 with 3 open positions', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_names_winning_store_number')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Store #1230 with 3 open positions', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_positions_count')

    def test_equivalent_comparison_by_loser_passes(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Store 1230 has 5 open positions; store 954 has 3 open positions, so #954 has fewer.', after=genuine_after())
        self.assertPasses(verdict)

    def test_read_only_write_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_saved(2, "CP-5991-12522")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'read_only_saved_jobs_unchanged')

    def test_store_number_inside_requisition_id_does_not_count(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, "CP-1230-11592 has 5 openings"), "answer_names_winning_store_number")


if __name__ == "__main__":
    unittest.main()
