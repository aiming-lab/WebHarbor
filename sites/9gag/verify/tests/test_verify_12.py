from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import USERS, State, VerifierTestCase, login_steps, step  # noqa: E402

BOB, EMAIL, _ = USERS["bob"]
ORIGINAL = "/gag/an-engineer-explains-why-this-bridge-hums-in-the-wind-19"
COMMENT = "Resonance makes ordinary structures fascinating."
GENUINE_STEPS = login_steps(EMAIL) + [
    step("/home"), step("/interest/science"), step("/interest/science?page=2"),
    step(ORIGINAL, "input", COMMENT), step(ORIGINAL, "click"), step(ORIGINAL + "#comments", "done"),
]
ANSWER = "Comment posted on the humming bridge post."


def genuine_after() -> State:
    return State().add_comment(BOB, 19, COMMENT)


class VerifyTask12Tests(VerifierTestCase):
    N = 12

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after()))

    def test_noop_run_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ""), "final_answer_nonempty")

    def test_shortcut_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ANSWER, after=genuine_after()), "visited_login_page")

    def test_state_mismatch_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER), "comment_exact_delta")

    def test_wrong_comment_text_fails(self) -> None:
        after = State().add_comment(BOB, 19, "Resonance makes ordinary structures boring.")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "comment_exact_delta")

    def test_trailing_period_and_case_are_tolerated(self) -> None:
        after = State().add_comment(BOB, 19, "resonance makes ordinary structures fascinating")
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=after))

    def test_comment_on_remix_fails(self) -> None:
        after = State().add_comment(BOB, 54, COMMENT)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "comment_exact_delta")

    def test_duplicate_comment_fails(self) -> None:
        after = genuine_after().add_comment(BOB, 19, COMMENT)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "comment_exact_delta")

    def test_comment_without_counter_bump_fails(self) -> None:
        after = State().add_comment(BOB, 19, COMMENT, bump=False)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "post_19_counters_exact_delta")

    def test_wrong_account_fails(self) -> None:
        steps = login_steps(USERS["carol"][1]) + [step("/interest/science"), step(ORIGINAL, "done")]
        after = State().add_comment(USERS["carol"][0], 19, COMMENT)
        self.assertFailsOn(self.verdict(steps, ANSWER, after=after), "entered_expected_account_identity")


if __name__ == "__main__":
    unittest.main()
