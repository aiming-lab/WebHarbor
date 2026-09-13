from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import USERS, State, VerifierTestCase, login_steps, step  # noqa: E402

ALICE, EMAIL, _ = USERS["alice"]
ORIGINAL = "/gag/tiny-lighthouse-office-with-the-best-ocean-view-12"
REMIX = "/gag/community-remix-2-tiny-lighthouse-office-with-the-best-ocean-view-47"
GENUINE_STEPS = login_steps(EMAIL) + [
    step("/home", "input", "lighthouse office"),
    step("/search?q=lighthouse+office"),
    step(ORIGINAL, "click"),
    step(ORIGINAL, "done"),
]
ANSWER = "Saved 'Tiny lighthouse office with the best ocean view' to Alice's collection."


def genuine_after() -> State:
    return State().add_saved(ALICE, 12)


class VerifyTask10Tests(VerifierTestCase):
    N = 10

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after()))

    def test_run_dir_snapshots_are_discovered(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after(), snapshots_in_run_dir=True))

    def test_noop_run_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ""), "final_answer_nonempty")

    def test_shortcut_fails_on_login_gate(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ANSWER, after=genuine_after()), "visited_login_page")

    def test_state_mismatch_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER), "saved_post_exact_delta")

    def test_saving_the_remix_clone_fails(self) -> None:
        steps = login_steps(EMAIL) + [step("/search?q=lighthouse+office"), step(REMIX, "click"), step(REMIX, "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=State().add_saved(ALICE, 47)), "visited_original_post_detail")

    def test_wrong_account_fails(self) -> None:
        steps = login_steps(USERS["bob"][1]) + [step("/search?q=lighthouse"), step(ORIGINAL, "done")]
        after = State().add_saved(USERS["bob"][0], 12)
        self.assertFailsOn(self.verdict(steps, ANSWER, after=after), "entered_expected_account_identity")

    def test_collateral_write_fails(self) -> None:
        after = genuine_after().add_vote(ALICE, 12, 1)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "no_collateral_writes")

    def test_extra_save_fails(self) -> None:
        after = genuine_after().add_saved(ALICE, 47)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "saved_post_exact_delta")

    def test_missing_search_visit_fails(self) -> None:
        steps = login_steps(EMAIL) + [step(ORIGINAL, "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_search_results")

    def test_login_after_save_fails_order(self) -> None:
        steps = [step("/"), step("/search?q=lighthouse"), step(ORIGINAL, "click")] + login_steps(EMAIL)
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "workflow_login_before_save")

    def test_initial_snapshot_with_extra_row_fails_closed(self) -> None:
        initial = State().add_saved(ALICE, 12)  # 17 saved rows: not the frozen seed
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=initial), "snapshot_contract_invalid")

    def test_already_saved_precondition_fails(self) -> None:
        initial = State().remove_saved(ALICE, 1).add_saved(ALICE, 12)  # same counts, target already saved
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, initial=initial, after=initial), "initial_state_requires_action")

    def test_mixed_origin_run_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after(), trajectory_updates={"start_url": "http://localhost:40026/"})
        self.assertFailsOn(verdict, "all_urls_match_local_origin")


if __name__ == "__main__":
    unittest.main()
