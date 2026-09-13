from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import USERS, State, VerifierTestCase, login_steps, step  # noqa: E402

CAROL, EMAIL, _ = USERS["carol"]
ORIGINAL = "/gag/dog-refuses-to-leave-the-kayak-after-the-trip-ends-20"
REMIX = "/gag/community-remix-10-dog-refuses-to-leave-the-kayak-after-the-trip-ends-55"
GENUINE_STEPS = login_steps(EMAIL) + [step("/home"), step("/interest/animals"), step(ORIGINAL, "click"), step(ORIGINAL, "done")]
ANSWER = "Upvoted the kayak dog post."


def genuine_after() -> State:
    return State().add_vote(CAROL, 20, 1)


class VerifyTask11Tests(VerifierTestCase):
    N = 11

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after()))

    def test_noop_run_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ""), "final_answer_nonempty")

    def test_shortcut_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ANSWER, after=genuine_after()), "visited_login_page")

    def test_state_mismatch_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER), "vote_exact_delta")

    def test_downvote_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=State().add_vote(CAROL, 20, -1)), "vote_exact_delta")

    def test_vote_on_remix_fails(self) -> None:
        steps = login_steps(EMAIL) + [step("/interest/animals"), step(REMIX, "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=State().add_vote(CAROL, 55, 1)), "visited_original_post_detail")

    def test_vote_row_without_counter_bump_fails(self) -> None:
        after = State().add_vote(CAROL, 20, 1, bump=False)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "post_20_counters_exact_delta")

    def test_counter_bump_on_other_post_fails(self) -> None:
        after = genuine_after().sql("UPDATE post SET up_votes = up_votes + 1 WHERE id = 21")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "post_20_counters_exact_delta")

    def test_collateral_save_fails(self) -> None:
        after = genuine_after().add_saved(CAROL, 12)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "no_collateral_writes")

    def test_search_instead_of_browse_fails(self) -> None:
        steps = login_steps(EMAIL) + [step("/search?q=kayak"), step(ORIGINAL, "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_animals_interest_feed")


if __name__ == "__main__":
    unittest.main()
