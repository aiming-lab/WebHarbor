from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "lillian-acosta-4a89e15e"
GENUINE_STEPS = [
    step("/"),
    step("/providers/specialty/obstetrics-gynecology"),
    step("/providers/specialty/obstetrics-gynecology/new-jersey"),
    step("/providers/specialty/obstetrics-gynecology/new-jersey/salem"),
    step(profile(SLUG), "done"),
]
ANSWER = "Staff was courteous had the most needs-improvement votes; average wait time 15 minutes."


def genuine_after() -> State:
    return State()

class VerifyTask7Tests(SharedVerifierTests, VerifierTestCase):
    N = 7
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), step("/results?q=OBGYN&loc=Salem%2C+NJ", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_wait_variants_pass(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, "Criterion: Staff was courteous (16). Wait: 15 min."))
        self.assertPasses(self.verdict(GENUINE_STEPS, "'Staff was courteous'; average wait time is 15"))

    def test_clock_time_is_not_wait_minutes(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, "Staff was courteous; office opens 9:15 am")
        self.assertFailsOn(verdict, "answer_has_wait_minutes")

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Gave a thorough Exam; average wait time 15 minutes', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_worst_criterion')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Staff was courteous; average wait time 45 minutes', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_wait_minutes')

    def test_read_only_write_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 156)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "read_only_saved_providers_unchanged")


if __name__ == "__main__":
    unittest.main()
