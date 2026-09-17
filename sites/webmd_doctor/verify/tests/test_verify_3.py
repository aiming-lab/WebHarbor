from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "mateo-alvarado-f727bd61"
GENUINE_STEPS = [
    step("/"),
    step("/providers/specialty/neurology"),
    step("/providers/specialty/neurology/pennsylvania"),
    step("/providers/specialty/neurology/pennsylvania/west-chester"),
    step(profile(SLUG), "done"),
]
ANSWER = "Providence Road Medical Group - Professional Plaza, 3543 Baltimore Pike Bldg B, Media, PA"


def genuine_after() -> State:
    return State()

class VerifyTask3Tests(SharedVerifierTests, VerifierTestCase):
    N = 3
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), step("/providers/specialty/neurology/pennsylvania/west-chester", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_dash_variants_pass(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, "Providence Road Medical Group – Professional Plaza at 3543 Baltimore Pike"))

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Goose Creek Neurology Group, 1315 W Chester Pike Ste 300', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_other_office_name')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Providence Road Medical Group - Professional Plaza, 3534 Baltimore Pike', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_other_office_street')

    def test_read_only_write_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 75)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "read_only_saved_providers_unchanged")


if __name__ == "__main__":
    unittest.main()
