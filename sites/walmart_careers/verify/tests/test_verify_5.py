from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    step("/results"),
    step("/results?area=technology&type=Full+time"),
    step("/results?area=technology&type=Full+time&loc=Hoboken%2C+NJ&radius=25"),
    step("/jobs/R-2411489", "done"),
]
ANSWER = "R-2411489 / Option 1: Bachelor's degree in computer science, computer information systems, or related area"


def genuine_after() -> State:
    after = State()
    pass
    return after


class VerifyTask5Tests(VerifierTestCase):
    N = 5

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
        steps = [step("/"), step("/results?area=technology&type=Full+time&loc=Hoboken%2C+NJ&radius=25", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_job_detail_R-2411489')

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, "R-2411489 / Master's degree in computer science", after=genuine_after())
        self.assertFailsOn(verdict, 'answer_names_option_1_degree')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, "R-2424873 / Bachelor's degree in computer science", after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_requisition_id')

    def test_read_only_write_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_saved(2, "CP-5991-12522")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'read_only_saved_jobs_unchanged')

    def test_location_only_results_gate_fails(self) -> None:
        steps = [step("/"), step("/results?q=engineer&loc=hoboken&radius=25"), step("/jobs/R-2411489", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_results_required_filters")

    def test_plain_search_results_fail_gate(self) -> None:
        steps = [step("/"), step("/results?q=senior+software+engineer"), step("/jobs/R-2411489", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_results_required_filters")

    def test_typed_search_without_filters_fails_gate(self) -> None:
        steps = [step("/"), step("/results?q=Technology+Hoboken%2C+NJ"), step("/jobs/R-2411489", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_results_required_filters")


if __name__ == "__main__":
    unittest.main()
