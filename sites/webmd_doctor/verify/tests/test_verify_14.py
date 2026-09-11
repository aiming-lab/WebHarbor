from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

WINNER = "arjun-bouchard-f3c85053"
OTHER = "colin-ellery-640b0a4a"
HOSPITAL = "/hospital/christina-creek-medical-center"
GENUINE_STEPS = [
    step("/"),
    step("/hospitals"),
    step("/hospitals/delaware"),
    step(HOSPITAL),
    step(HOSPITAL + "?specialty=psychiatry"),
    step(profile(WINNER)),
    step(HOSPITAL + "?specialty=psychiatry"),
    step(profile(OTHER), "done"),
]
ANSWER = "Dr. Arjun Bouchard was certified more recently (2004; Dr. Ellery in 2000)."


def genuine_after() -> State:
    return State()

class VerifyTask14Tests(SharedVerifierTests, VerifierTestCase):
    N = 14
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), step("/results?q=Psychiatrist"), step(profile(WINNER)), step(profile(OTHER), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_delaware_hospitals_page")

    def test_hospital_page_skipped_fails(self) -> None:
        steps = [step("/"), step("/hospitals/delaware"), step(profile(WINNER)), step(profile(OTHER), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_hospital_page")

    def test_only_one_profile_fails(self) -> None:
        steps = [step("/"), step("/hospitals/delaware"), step(HOSPITAL), step(profile(WINNER), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + OTHER)

    def test_other_specialty_pair_fails(self) -> None:
        steps = [step("/"), step("/hospitals/delaware"), step(HOSPITAL), step(profile("kevin-hargrove-270f73e2")), step(profile("quinn-pereira-219e1bc1"), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + WINNER)

    def test_paginated_roster_passes(self) -> None:
        steps = [step("/"), step("/hospitals/delaware"), step(HOSPITAL), step(HOSPITAL + "?pagenumber=2"), step(profile(WINNER)), step(profile(OTHER), "done")]
        self.assertPasses(self.verdict(steps, ANSWER))

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Dr. Colin Ellery was certified more recently, in 2000.', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_names_more_recent_certification')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Arjun Bouchard, certified 1997', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_certification_year')

    def test_read_only_write_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 121)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "read_only_saved_providers_unchanged")


if __name__ == "__main__":
    unittest.main()
