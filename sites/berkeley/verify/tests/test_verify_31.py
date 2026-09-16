from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, step,
)

MSRI_ID = 9
CPL_ID = 22
GENUINE_STEPS = [
    *login_steps("bob@berkeley.edu"),
    step("/research/msri"),
    step("/research/msri", "click"),
    step("/research/cpl"),
    step("/research/cpl", "click"),
    step("/account"),
    step("/account", "click"),
    step("/account", "done"),
]
ANSWER = (
    "I signed in as bob, saved both centers in order, then removed the Mathematical Sciences "
    "Research Institute bookmark. The California Policy Lab remains saved; its director is "
    "Prof. Jesse Rothstein."
)


def _saved_then_removed() -> State:
    """The genuine history: MSRI takes row id 1, CPL row id 2, then MSRI is deleted."""
    state = State()
    state.add_bookmark(2, "research", MSRI_ID)   # id 1
    state.add_bookmark(2, "research", CPL_ID)    # id 2
    state.remove_bookmark(1)
    return state


class VerifyTask31Tests(SharedVerifierTests, VerifierTestCase):
    N = 31
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return _saved_then_removed()

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=self.genuine_after()))

    def test_skipped_removal_fails_on_delta(self) -> None:
        after = State()
        after.add_bookmark(2, "research", MSRI_ID)   # id 1
        after.add_bookmark(2, "research", CPL_ID)    # id 2
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "bookmarks_exact_delta")

    def test_nothing_added_fails_on_delta(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, ANSWER)
        self.assertFailsOn(verdict, "bookmarks_exact_delta")

    def test_wrong_add_order_fails_on_row_id_pin(self) -> None:
        """The trajectory matches, but the DB proves CPL was saved before MSRI (survivor id 1)."""
        after = State()
        after.add_bookmark(2, "research", CPL_ID)    # id 1
        after.add_bookmark(2, "research", MSRI_ID)   # id 2
        after.remove_bookmark(2)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "bookmarks_surviving_row_ids")

    def test_removing_the_wrong_centre_fails_on_delta(self) -> None:
        after = State()
        after.add_bookmark(2, "research", MSRI_ID)   # id 1
        after.add_bookmark(2, "research", CPL_ID)    # id 2
        after.remove_bookmark(2)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "bookmarks_exact_delta")

    def test_missing_login_fails(self) -> None:
        steps = GENUINE_STEPS[len(login_steps("bob@berkeley.edu")):]
        self.assertFailsOn(
            self.verdict(steps, ANSWER, after=self.genuine_after()), "visited_login_page"
        )

    def test_single_account_visit_fails_workflow(self) -> None:
        steps = [
            *login_steps("bob@berkeley.edu"),
            step("/research/msri"), step("/research/msri", "click"),
            step("/research/cpl"), step("/research/cpl", "click"),
            step("/account", "done"),
        ]
        self.assertFailsOn(
            self.verdict(steps, ANSWER, after=self.genuine_after()), "workflow_in_order"
        )

    def test_wrong_remaining_director_fails(self) -> None:
        answer = ANSWER.replace("Jesse Rothstein", "Tatiana Toro")
        self.assertFailsOn(
            self.verdict(GENUINE_STEPS, answer, after=self.genuine_after()), "answer_has_remaining_director"
        )

    def test_negated_removal_fails(self) -> None:
        answer = (
            "The California Policy Lab (director: Prof. Jesse Rothstein) remains saved, but the "
            "Mathematical Sciences Research Institute bookmark was not removed."
        )
        self.assertFailsOn(
            self.verdict(GENUINE_STEPS, answer, after=self.genuine_after()), "answer_confirms_removal"
        )

    def test_collateral_write_for_another_user_fails(self) -> None:
        after = self.genuine_after()
        after.add_bookmark(1, "research", 8)  # alice, not bob
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "bookmarks_other_users_unchanged")

    def test_alternative_phrasing_passes(self) -> None:
        answer = (
            "Bob saved both centers, then removed the MSRI bookmark; the California Policy Lab "
            "is still saved (director: Prof. Jesse Rothstein)."
        )
        self.assertPasses(self.verdict(GENUINE_STEPS, answer, after=self.genuine_after()))

    def test_unrelated_bookmark_write_fails_on_delta(self) -> None:
        after = self.genuine_after()
        after.add_bookmark(2, "program", 41)  # collateral write for the same user
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "bookmarks_exact_delta")


if __name__ == "__main__":
    unittest.main()
