from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    step("/", "input", "freight handler"),
    step("/results?q=freight+handler"),
    step("/jobs/CP-9054-10921", "done"),
]
ANSWER = 'Shift may start between 6:00pm - 3:00am / 3 open positions'


def genuine_after() -> State:
    after = State()
    pass
    return after


class VerifyTask2Tests(VerifierTestCase):
    N = 2

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
        steps = [step("/"), step("/results?q=freight+handler", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_job_detail_CP-9054-10921')

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Shift may start between 9:00pm - 1:30am / 4 open positions', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_shift_window')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Shift may start between 6:00pm - 3:00am / 4 open positions', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_positions_count')

    def test_read_only_write_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_saved(2, "CP-5991-12522")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'read_only_saved_jobs_unchanged')

    def test_count_attached_to_years_fails(self) -> None:
        answer = "The shift is 6:00pm - 3:00am and the role requires 3 years of experience."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_positions_count")

    def test_time_format_variants_pass(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, "Starts 6 PM to 3 a.m.; three positions"))
        self.assertPasses(self.verdict(GENUINE_STEPS, "18:00-03:00, 3 openings"))


if __name__ == "__main__":
    unittest.main()
