from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import USERS, State, VerifierTestCase, login_steps, step  # noqa: E402

DAVID, EMAIL, _ = USERS["david"]
SOLAR = "/gag/solar-powered-camping-setup-survives-a-rainy-weekend-11"
BRIDGE = "/gag/an-engineer-explains-why-this-bridge-hums-in-the-wind-19"
BALLOON = "/gag/students-launch-a-weather-balloon-with-a-tiny-rubber-duck-25"
GENUINE_STEPS = login_steps(EMAIL) + [
    step("/home"), step("/interest/science"), step(BALLOON), step("/interest/science"), step("/interest/science?page=2"),
    step(SOLAR), step("/interest/science?page=2"), step(BRIDGE, "click"), step(BRIDGE, "done"),
]
ANSWER = "Compared 120 W, 440 Hz and 27 km; saved the humming bridge post (440 is the largest)."


def genuine_after() -> State:
    return State().add_saved(DAVID, 19)


class VerifyTask19Tests(VerifierTestCase):
    N = 19

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after()))

    def test_noop_run_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ""), "final_answer_nonempty")

    def test_shortcut_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ANSWER, after=genuine_after()), "visited_login_page")

    def test_state_mismatch_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER), "saved_post_exact_delta")

    def test_saving_the_wrong_post_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=State().add_saved(DAVID, 11)), "saved_post_exact_delta")

    def test_skipping_a_compared_detail_page_fails(self) -> None:
        steps = login_steps(EMAIL) + [step("/interest/science"), step(BRIDGE), step(SOLAR), step(BRIDGE, "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_compared_detail_25")

    def test_wrong_account_fails(self) -> None:
        steps = login_steps(USERS["alice"][1]) + GENUINE_STEPS[5:]
        after = State().add_saved(USERS["alice"][0], 19)
        self.assertFailsOn(self.verdict(steps, ANSWER, after=after), "entered_expected_account_identity")

    def test_two_saves_fail(self) -> None:
        after = genuine_after().add_saved(DAVID, 11)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "saved_post_exact_delta")

    def test_collateral_write_fails(self) -> None:
        after = genuine_after().add_vote(DAVID, 19, 1)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "no_collateral_writes")


if __name__ == "__main__":
    unittest.main()
