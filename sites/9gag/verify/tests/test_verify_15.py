from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import USERS, State, VerifierTestCase, login_steps, step  # noqa: E402

ALICE, EMAIL, USERNAME = USERS["alice"]
TITLE = "Quiet victories deserve confetti"
DESCRIPTION = "My neighbor finished night school after six years."
TAGS = "community|education|wholesome"
NEW = "/gag/quiet-victories-deserve-confetti"
GENUINE_STEPS = login_steps(EMAIL) + [
    step("/home"), step("/submit", "input", TITLE), step("/submit", "input", DESCRIPTION),
    step("/submit", "input", TAGS), step("/submit", "click"), step(NEW, "done"),
]
ANSWER = "Published the post; it is live at /gag/quiet-victories-deserve-confetti."


def genuine_after() -> State:
    return State().add_post(TITLE, DESCRIPTION, "wholesome", TAGS, USERNAME, slug="quiet-victories-deserve-confetti")


class VerifyTask15Tests(VerifierTestCase):
    N = 15

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after()))

    def test_noop_run_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ""), "final_answer_nonempty")

    def test_shortcut_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ANSWER, after=genuine_after()), "visited_login_page")

    def test_state_mismatch_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER), "new_post_exact_delta")

    def test_wrong_section_fails(self) -> None:
        after = State().add_post(TITLE, DESCRIPTION, "humor", TAGS, USERNAME, slug="quiet-victories-deserve-confetti")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_post_exact_delta")

    def test_wrong_tags_fail(self) -> None:
        after = State().add_post(TITLE, DESCRIPTION, "wholesome", "community|wholesome", USERNAME, slug="quiet-victories-deserve-confetti")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_post_exact_delta")

    def test_wrong_author_fails(self) -> None:
        after = State().add_post(TITLE, DESCRIPTION, "wholesome", TAGS, "bob_c", slug="quiet-victories-deserve-confetti")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_post_exact_delta")

    def test_two_posts_fail(self) -> None:
        after = genuine_after().add_post(TITLE, DESCRIPTION, "wholesome", TAGS, USERNAME, slug="quiet-victories-deserve-confetti-2")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_post_exact_delta")

    def test_published_page_not_opened_fails(self) -> None:
        steps = login_steps(EMAIL) + [step("/submit", "click"), step("/submit", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_published_post")

    def test_collateral_write_fails(self) -> None:
        after = genuine_after().add_saved(ALICE, 12)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "no_collateral_writes")


if __name__ == "__main__":
    unittest.main()
