from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    step("/careers-areas/healthcare"),
    step("/results?area=healthcare&category=pharmacy-services"),
    step("/jobs/CP-5260-11531", "done"),
]
ANSWER = '#pharmacytechjobs / 2 open positions'


def genuine_after() -> State:
    after = State()
    pass
    return after


class VerifyTask3Tests(VerifierTestCase):
    N = 3

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
        steps = [step("/"), step("/results?area=healthcare&category=pharmacy-services"), step("/jobs/CP-5260-11531", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_healthcare_area_page')

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, '#pharmacytechjobs / 3 open positions', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_positions_count')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, '#pharmacyjobs / 2 open positions', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_hashtag')

    def test_read_only_write_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_saved(2, "CP-5991-12522")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'read_only_saved_jobs_unchanged')

    def test_area_only_results_gate_passes(self) -> None:
        steps = [step("/"), step("/careers-areas/healthcare"), step("/results?area=healthcare"), step("/jobs/CP-5260-11531", "done")]
        self.assertPasses(self.verdict(steps, ANSWER))

    def test_results_without_area_or_category_fails(self) -> None:
        steps = [step("/"), step("/careers-areas/healthcare"), step("/results?q=pharmacy"), step("/jobs/CP-5260-11531", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_healthcare_results")


if __name__ == "__main__":
    unittest.main()
