from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    step("/results?q=delivery+search+arrival+matching"),
    step("/jobs/R-2456729"),
    step("/results?q=delivery+search+arrival+matching"),
    step("/jobs/R-2443374", "done"),
]
ANSWER = 'R-2456729 / 9 years'


def genuine_after() -> State:
    after = State()
    pass
    return after


class VerifyTask10Tests(VerifierTestCase):
    N = 10

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
        steps = [step("/"), step("/results?q=delivery+search"), step("/jobs/R-2456729", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_job_detail_R-2443374')

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'R-2443374 / 6 years', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_requisition_id')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'R-2456729 / 6 years', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_years_count')

    def test_read_only_write_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_saved(2, "CP-5991-12522")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'read_only_saved_jobs_unchanged')

    def test_years_word_form_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, "R-2456729 (Bentonville) requires nine years under Option 2"))


if __name__ == "__main__":
    unittest.main()
