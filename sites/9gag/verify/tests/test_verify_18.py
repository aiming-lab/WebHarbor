from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import USERS, State, VerifierTestCase, login_steps, step  # noqa: E402

ALICE, EMAIL, _ = USERS["alice"]
GENUINE_STEPS = login_steps(EMAIL) + [step("/home"), step("/saved", "click"), step("/saved", "done")]
ANSWER = "Removed the solar-powered rainy-weekend camping setup from Saved."


def genuine_after() -> State:
    return State().remove_saved(ALICE, 11)


class VerifyTask18Tests(VerifierTestCase):
    N = 18

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after()))

    def test_noop_run_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ""), "final_answer_nonempty")

    def test_shortcut_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ANSWER, after=genuine_after()), "visited_login_page")

    def test_state_mismatch_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER), "saved_post_exact_delta")

    def test_removing_another_saved_post_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=State().remove_saved(ALICE, 16)), "saved_post_exact_delta")

    def test_removing_two_posts_fails(self) -> None:
        after = genuine_after().remove_saved(ALICE, 16)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "saved_post_exact_delta")

    def test_saved_page_not_opened_fails(self) -> None:
        steps = login_steps(EMAIL) + [step("/gag/solar-powered-camping-setup-survives-a-rainy-weekend-11", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_saved_collection")

    def test_collateral_write_fails(self) -> None:
        after = genuine_after().add_hidden(ALICE, 11)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "no_collateral_writes")

    def test_initial_snapshot_with_missing_row_fails_closed(self) -> None:
        initial = State().remove_saved(ALICE, 11)  # 15 saved rows: not the frozen seed
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=initial), "snapshot_contract_invalid")

    def test_not_saved_initially_precondition_fails(self) -> None:
        initial = State().remove_saved(ALICE, 11).add_saved(ALICE, 12)  # same counts, target not saved
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=initial), "initial_state_requires_action")


if __name__ == "__main__":
    unittest.main()
