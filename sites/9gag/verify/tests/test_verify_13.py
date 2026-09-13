from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import USERS, State, VerifierTestCase, login_steps, step  # noqa: E402

CAROL, EMAIL, _ = USERS["carol"]
ORIGINAL = "/gag/the-office-plant-gets-an-employee-badge-26"
REMIX = "/gag/community-remix-16-the-office-plant-gets-an-employee-badge-61"
GENUINE_STEPS = login_steps(EMAIL) + [
    step("/home", "input", "office plant employee badge"), step("/search?q=office+plant+employee+badge"),
    step(ORIGINAL, "click"), step("/", "done"),
]
ANSWER = "Hidden the office plant post from Carol's feeds."


def genuine_after() -> State:
    return State().add_hidden(CAROL, 26)


class VerifyTask13Tests(VerifierTestCase):
    N = 13

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after()))

    def test_noop_run_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ""), "final_answer_nonempty")

    def test_shortcut_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ANSWER, after=genuine_after()), "visited_login_page")

    def test_state_mismatch_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER), "hidden_post_exact_delta")

    def test_hiding_the_remix_fails(self) -> None:
        steps = login_steps(EMAIL) + [step("/search?q=office+plant"), step(REMIX, "click"), step("/", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=State().add_hidden(CAROL, 61)), "visited_original_post_detail")

    def test_collateral_write_fails(self) -> None:
        after = genuine_after().add_saved(CAROL, 26)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "no_collateral_writes")

    def test_missing_search_fails(self) -> None:
        steps = login_steps(EMAIL) + [step(ORIGINAL, "click"), step("/", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_search_results")


if __name__ == "__main__":
    unittest.main()
