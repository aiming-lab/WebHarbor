from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, step,
)

GENUINE_STEPS = [step("/"), step("/departments"), step("/departments/eecs", "done")]
ANSWER = "The chair of EECS is Prof. James Demmel, and the department is located at 253 Cory Hall."


class VerifyTask13Tests(SharedVerifierTests, VerifierTestCase):
    N = 13
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_shortcut_from_listing_fails(self) -> None:
        steps = [step("/"), step("/departments", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_department_detail")

    def test_real_world_chair_fails(self) -> None:
        answer = "The EECS chair is Prof. Alexei Efros, in 253 Cory Hall."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_chair")

    def test_wrong_location_fails(self) -> None:
        answer = "The chair of EECS is Prof. James Demmel, located in Soda Hall."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_location")

    def test_negated_chair_fails(self) -> None:
        answer = "James Demmel is not the chair of EECS."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_chair")

    def test_negated_titled_chair_fails(self) -> None:
        """C2 regression: the negation sits before the name, after "is" and the
        title's period — the abbreviation must not hide it."""
        answer = ("The chair of EECS is not Prof. James Demmel, and the department is "
                  "located at 253 Cory Hall.")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_chair")

    def test_alternative_phrasing_passes(self) -> None:
        answer = "EECS is chaired by James Demmel; its location is Cory Hall."
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "faculty", 1)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
