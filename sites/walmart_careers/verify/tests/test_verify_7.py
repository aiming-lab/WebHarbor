from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    step("/results"),
    step("/results?area=students&brand=Sam%27s+Club&type=Intern"),
    step("/jobs/R-2447168", "done"),
]
ANSWER = 'Intern (Fixed Term) / 2101 SE Simple Savings Dr'


def genuine_after() -> State:
    after = State()
    pass
    return after


class VerifyTask7Tests(VerifierTestCase):
    N = 7

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
        steps = [step("/"), step("/results?area=students&brand=Sam%27s+Club&type=Intern", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_job_detail_R-2447168')

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Regular/Permanent / 702 SW 8th St', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_worker_type_chip')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Intern (Fixed Term) / 702 SW 8th St', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_street_address')

    def test_read_only_write_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_saved(2, "CP-5991-12522")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'read_only_saved_jobs_unchanged')

    def test_required_filter_missing_fails_gate(self) -> None:
        for query in ("area=students&type=Intern", "area=students&brand=Sam%27s+Club", "type=Intern&brand=Sam%27s+Club"):
            with self.subTest(query=query):
                steps = [step("/"), step("/results?" + query), step("/jobs/R-2447168", "done")]
                self.assertFailsOn(self.verdict(steps, ANSWER), "visited_results_required_filters")


if __name__ == "__main__":
    unittest.main()
