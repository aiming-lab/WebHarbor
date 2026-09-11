from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "julian-zamora-d412b77d"
GENUINE_STEPS = [
    step("/"),
    step("/providers/specialty/cardiovascular-disease"),
    step("/providers/specialty/cardiovascular-disease/delaware"),
    step("/providers/specialty/cardiovascular-disease/delaware/wilmington"),
    step(profile(SLUG), "done"),
]
ANSWER = "NPI 1438496704; languages: English, Tagalog and Portuguese."


def genuine_after() -> State:
    return State()

class VerifyTask1Tests(SharedVerifierTests, VerifierTestCase):
    N = 1
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), step("/results?q=Cardiologist", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_other_zamora_profile_fails(self) -> None:
        steps = [step("/"), step(profile("ana-zamora-00000000"), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_grouped_npi_passes(self) -> None:
        steps = [step("/"), step("/results?q=Cardiologist&loc=Wilmington%2C+DE"), step(profile(SLUG), "done")]
        self.assertPasses(self.verdict(steps, "NPI: 1438 496 704. Speaks English, Tagalog, Portuguese."))

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'NPI 1438496705; English, Tagalog, Portuguese', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_npi')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'NPI 1438496704; English and Tagalog', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_lists_languages')

    def test_wrong_answer_2_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'NPI 1438496704; English, Tagalog, not Portuguese', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_lists_languages')

    def test_read_only_write_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 28)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "read_only_saved_providers_unchanged")


if __name__ == "__main__":
    unittest.main()
