from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, login_steps, only_paths, step  # noqa: E402,F401

GENUINE_STEPS = [
    step("/"),
    step("/", "input", "staff software engineer"),
    step("/results?q=staff+software+engineer"),
    step("/jobs/R-2468347", "done"),
]
ANSWER = "Option 2: 7 years' experience in software engineering or related area, including experience operating search or ML-serving systems in production."


def genuine_after() -> State:
    after = State()
    pass
    return after


class VerifyTask1Tests(VerifierTestCase):
    N = 1

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
        steps = [step("/"), step("/results?q=staff+software+engineer", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), 'visited_job_detail_R-2468347')

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, "Option 1: Bachelor's degree in computer science, computer engineering, computer information systems, software engineering, or related area and 5 years' experience in software engineering or related area, including experience operating search or ML-serving systems in production.", after=genuine_after())
        self.assertFailsOn(verdict, 'answer_quotes_option_2')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, "7 years' experience in software engineering or related area, including experience building high-volume checkout or payments services.", after=genuine_after())
        self.assertFailsOn(verdict, 'answer_quotes_option_2')

    def test_read_only_application_fails(self) -> None:
        initial = State()
        after = genuine_after()
        after.add_application("CP-9054-10921", 2, "bob.c@test.com", "206-555-0178")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=after), 'read_only_applications_unchanged')

    def test_curly_quotes_and_case_pass(self) -> None:
        answer = "7 YEARS’ EXPERIENCE IN SOFTWARE ENGINEERING OR RELATED AREA, INCLUDING EXPERIENCE OPERATING SEARCH OR ML-SERVING SYSTEMS IN PRODUCTION."
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_truncated_option_two_quote_fails(self) -> None:
        answer = "7 years' experience operating search or ML-serving systems in production"
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_quotes_option_2")


if __name__ == "__main__":
    unittest.main()
