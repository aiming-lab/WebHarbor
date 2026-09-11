from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "linda-merriweather-378753c8"
PRACTICE = "/practice/rose-tree-orthopedics-sports-medicine"
GENUINE_STEPS = [
    step("/"),
    step("/choice-awards"),
    step("/choice-awards/awardrecipients?award-class=patient"),
    step("/choice-awards/awardrecipients?award-class=patient&page=2"),
    step(profile(SLUG)),
    step(PRACTICE, "done"),
]
ANSWER = "Website: https://www.rosetreeorthopedicssportsmedicine.example - Saturday 9:00 am - 2:00 pm."


def genuine_after() -> State:
    return State()

class VerifyTask15Tests(SharedVerifierTests, VerifierTestCase):
    N = 15
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), step(profile(SLUG)), step(PRACTICE, "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_award_page")

    def test_wrong_award_class_fails(self) -> None:
        steps = [step("/"), step("/choice-awards"), step("/choice-awards/awardrecipients?award-class=elite"), step(profile(SLUG)), step(PRACTICE, "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_patients_choice_recipients_page")

    def test_practice_page_skipped_fails(self) -> None:
        steps = [step("/"), step("/choice-awards"), step("/choice-awards/awardrecipients"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_practice_page")

    def test_default_award_class_and_state_filter_pass(self) -> None:
        steps = [step("/"), step("/choice-awards"), step("/choice-awards/awardrecipients"), step("/choice-awards/awardrecipients?award-class=patient&state=pennsylvania"),
                 step(profile(SLUG)), step(PRACTICE, "done")]
        self.assertPasses(self.verdict(steps, "rosetreeorthopedicssportsmedicine.example, Sat 9 AM-2 PM"))

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Website: https://www.rosetreeorthopedicssportsmedicine.com - Saturday 9:00 am - 2:00 pm', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_practice_website')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'Website: https://www.rosetreeorthopedicssportsmedicine.example - Saturday 8:00 am - 1:00 pm', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_saturday_hours')

    def test_read_only_write_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 100)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "read_only_saved_providers_unchanged")


if __name__ == "__main__":
    unittest.main()
