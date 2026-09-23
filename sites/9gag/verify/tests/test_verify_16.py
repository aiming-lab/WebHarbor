from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import USERS, State, VerifierTestCase, login_steps, step  # noqa: E402

ALICE, EMAIL, _ = USERS["alice"]
BIO = "Memes, trail photos, and excellent tiny libraries."
GENUINE_STEPS = login_steps(EMAIL) + [
    step("/home"), step("/settings", "input", "Alice J."), step("/settings", "input", BIO),
    step("/settings", "input", "Tacoma, WA"), step("/settings", "click"), step("/settings", "done"),
]
ANSWER = "Profile updated: display name, bio and location saved."


def genuine_after() -> State:
    return State().set_profile(ALICE, display_name="Alice J.", bio=BIO, location="Tacoma, WA")


class VerifyTask16Tests(VerifierTestCase):
    N = 16

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after()))

    def test_noop_run_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ""), "final_answer_nonempty")

    def test_shortcut_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ANSWER, after=genuine_after()), "visited_login_page")

    def test_state_mismatch_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER), "profile_fields_updated")

    def test_partial_update_fails(self) -> None:
        after = State().set_profile(ALICE, display_name="Alice J.", bio=BIO)  # location untouched
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "profile_fields_updated")

    def test_wrong_user_updated_fails(self) -> None:
        after = State().set_profile(USERS["bob"][0], display_name="Alice J.", bio=BIO, location="Tacoma, WA")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "profile_fields_updated")

    def test_password_change_fails(self) -> None:
        after = genuine_after().set_profile(ALICE, password_hash="scrypt:32768:8:1$x$y")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "user_exact_delta")

    def test_second_user_changed_fails(self) -> None:
        after = genuine_after().set_profile(USERS["bob"][0], location="Nowhere")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "user_exact_delta")

    def test_collateral_write_fails(self) -> None:
        after = genuine_after().add_saved(ALICE, 12)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "no_collateral_writes")

    def test_settings_page_not_opened_fails(self) -> None:
        steps = login_steps(EMAIL) + [step("/account", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER, after=genuine_after()), "visited_settings_page")


if __name__ == "__main__":
    unittest.main()
