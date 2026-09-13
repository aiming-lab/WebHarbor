from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import State, VerifierTestCase, step  # noqa: E402

EMAIL, USERNAME, PASSWORD = "river.reader@test.com", "river_reader", "RiverRead123!"
GENUINE_STEPS = [
    step("/"), step("/login"), step("/register", "input", EMAIL), step("/register", "input", USERNAME),
    step("/register", "input", PASSWORD), step("/register", "click"), step("/home", "done"),
]
ANSWER = "Account created and signed in; the header shows river_reader."


def genuine_after() -> State:
    return State().add_user(EMAIL, USERNAME, PASSWORD)


class VerifyTask17Tests(VerifierTestCase):
    N = 17

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER, after=genuine_after()))

    def test_noop_run_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ""), "final_answer_nonempty")

    def test_shortcut_fails(self) -> None:
        self.assertFailsOn(self.verdict([step("/", "done")], ANSWER, after=genuine_after()), "visited_register_page")

    def test_state_mismatch_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER), "new_user_exact_delta")

    def test_wrong_password_fails(self) -> None:
        after = State().add_user(EMAIL, USERNAME, "WrongPass123!")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_user_password_verifies")

    def test_wrong_username_fails(self) -> None:
        after = State().add_user(EMAIL, "river.reader", PASSWORD)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_user_exact_delta")

    def test_answer_without_username_fails(self) -> None:
        self.assertFailsOn(self.verdict(GENUINE_STEPS, "Done.", after=genuine_after()), "answer_confirms_header_username")

    def test_existing_user_edited_fails(self) -> None:
        after = genuine_after().set_profile(1, display_name="Alice X")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "new_user_exact_delta")

    def test_collateral_write_fails(self) -> None:
        after = genuine_after().add_saved(1, 12)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "no_collateral_writes")


if __name__ == "__main__":
    unittest.main()
