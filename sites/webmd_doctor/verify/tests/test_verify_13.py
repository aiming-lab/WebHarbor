from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

WINNER = "emerson-huang-f6afead5"
OTHER = "gregory-greenwood-34670192"
GENUINE_STEPS = [
    step("/"),
    step("/providers/specialty/dermatology"),
    step("/providers/specialty/dermatology/delaware"),
    step("/providers/specialty/dermatology/delaware/wilmington"),
    step(profile(OTHER)),
    step("/providers/specialty/dermatology/delaware/wilmington"),
    step(profile(WINNER), "done"),
]
ANSWER = "Dr. Emerson Huang graduated earlier, in 1992 (Dr. Greenwood graduated in 1997)."


def genuine_after() -> State:
    return State()

class VerifyTask13Tests(SharedVerifierTests, VerifierTestCase):
    N = 13
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), step("/providers/specialty/dermatology/delaware/wilmington", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + WINNER)

    def test_only_winner_profile_fails(self) -> None:
        steps = [step("/"), step(profile(WINNER), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + OTHER)

    def test_same_surname_other_doctor_fails(self) -> None:
        steps = [step("/"), step(profile(OTHER)), step(profile("tariq-huang-c8120504"), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + WINNER)

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Dr. Gregory Greenwood graduated earlier, in 1997.', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_names_earlier_graduate')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Dr. Huang, 1992', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_names_earlier_graduate')

    def test_wrong_answer_2_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Emerson Huang, DO - 1997', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_graduation_year')

    def test_read_only_write_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 7)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "read_only_saved_providers_unchanged")


    def test_year_attributed_to_loser_fails(self) -> None:
        bad = "Dr. Gregory Greenwood graduated earlier, in 1992 (Dr. Emerson Huang in 1997)."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, bad), "answer_binds_winner_to_year")

    def test_split_name_tokens_fail(self) -> None:
        # Both name tokens exist but never as the contiguous winner full name;
        # the old order-free contains_doctor_name check passes this, so the
        # comparison binding is the check that must reject it.
        bad = "Emerson Jones was compared; Tariq Huang graduated in 1992."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, bad), "answer_binds_winner_to_year")


if __name__ == "__main__":
    unittest.main()
