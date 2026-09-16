from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, step,
)

CENTRE_ID = 8  # Berkeley Seismological Laboratory (slug seismo-lab)
GENUINE_STEPS = [
    *login_steps("alice@berkeley.edu"),
    step("/research/seismo-lab"),
    step("/research/seismo-lab", "click"),
    step("/account"),
    step("/account", "done"),
]
ANSWER = (
    "I signed in as alice, saved the Berkeley Seismological Laboratory to my bookmarks, and it "
    "is listed under My Account. Its director is Prof. Douglas Dreger."
)


class VerifyTask30Tests(SharedVerifierTests, VerifierTestCase):
    N = 30
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        state = State()
        state.add_bookmark(1, "research", CENTRE_ID)
        return state

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=self.genuine_after()))

    def test_state_mismatch_without_save_fails_on_delta(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, ANSWER)  # agent self-reports success, DB untouched
        self.assertFailsOn(verdict, "bookmarks_exact_delta")

    def test_saving_the_wrong_centre_fails_on_delta(self) -> None:
        after = State()
        after.add_bookmark(1, "research", 1)  # BAIR, not the named centre
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "bookmarks_exact_delta")

    def test_duplicate_save_fails_on_delta(self) -> None:
        after = State()
        after.add_bookmark(1, "research", CENTRE_ID, row_id=1)
        after.add_bookmark(1, "research", CENTRE_ID, row_id=2)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "bookmarks_exact_delta")

    def test_saving_under_another_account_fails_on_delta(self) -> None:
        after = State()
        after.add_bookmark(2, "research", CENTRE_ID)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "bookmarks_exact_delta")

    def test_missing_login_fails(self) -> None:
        steps = [step("/research/seismo-lab"), step("/research/seismo-lab", "click"),
                 step("/account"), step("/account", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=self.genuine_after()), "visited_login_page")

    def test_signing_in_as_the_wrong_account_fails(self) -> None:
        steps = [
            *login_steps("bob@berkeley.edu"),
            step("/research/seismo-lab"), step("/research/seismo-lab", "click"),
            step("/account"), step("/account", "done"),
        ]
        self.assertFailsOn(
            self.verdict(steps, ANSWER, after=self.genuine_after()), "entered_expected_account_email"
        )

    def test_missing_centre_page_fails_workflow(self) -> None:
        steps = [*login_steps("alice@berkeley.edu"), step("/account"), step("/account", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=self.genuine_after()), "workflow_in_order")

    def test_negated_save_fails(self) -> None:
        answer = "I did not save the Berkeley Seismological Laboratory."
        verdict = self.verdict(GENUINE_STEPS, answer, after=self.genuine_after())
        self.assertFailsOn(verdict, "answer_has_centre")

    def test_wrong_director_fails(self) -> None:
        answer = ANSWER.replace("Douglas Dreger", "David Culler")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer, after=self.genuine_after()), "answer_has_director")

    def test_alternative_phrasing_passes(self) -> None:
        answer = (
            "Logged in as alice@berkeley.edu; the Berkeley Seismological Laboratory now appears "
            "in My Bookmarks, directed by Douglas Dreger."
        )
        self.assertPasses(self.verdict(GENUINE_STEPS, answer, after=self.genuine_after()))

    def test_registration_write_fails(self) -> None:
        after = self.genuine_after()
        after.extra_sql.append(
            "INSERT INTO users(id, email, username, password_hash, full_name, role, bio, created_at) "
            "VALUES (99, 'eve@berkeley.edu', 'eve', 'x', 'Eve', 'student', '', '2026-05-12 00:00:00')"
        )
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_users_unchanged")


if __name__ == "__main__":
    unittest.main()
