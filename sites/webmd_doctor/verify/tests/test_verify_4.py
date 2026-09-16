from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "charles-villanueva-13e969b2"
GENUINE_STEPS = [
    step("/"),
    step("/providers/specialty/orthopedic-surgery"),
    step("/providers/specialty/orthopedic-surgery/maryland"),
    step("/providers/specialty/orthopedic-surgery/maryland/elkton"),
    step(profile(SLUG), "done"),
]
ANSWER = "Certified by the American Board of Orthopaedic Surgery in 2014; residency at Blue Ridge Regional Medical Center."


def genuine_after() -> State:
    return State()

class VerifyTask4Tests(SharedVerifierTests, VerifierTestCase):
    N = 4
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), step("/results?q=Orthopedic+Surgeon&loc=Elkton%2C+MD", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_american_spelling_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, "American Board of Orthopedic Surgery (2014), residency: Blue Ridge Regional Medical Center"))

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'American Board of Surgery, 2014, Blue Ridge Regional Medical Center', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_certifying_board')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'American Board of Orthopaedic Surgery, 2013, Blue Ridge Regional Medical Center', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_certification_year')

    def test_wrong_answer_2_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'American Board of Orthopaedic Surgery, 2014, Cumberland Ridge Hospital', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_residency')

    def test_read_only_write_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 92)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "read_only_saved_providers_unchanged")


if __name__ == "__main__":
    unittest.main()
