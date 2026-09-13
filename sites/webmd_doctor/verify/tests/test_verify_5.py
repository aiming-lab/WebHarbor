from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, login_steps, only_paths, profile, signup_steps, step,
)

SLUG = "caroline-danforth-7093653d"
GENUINE_STEPS = [
    step("/"),
    step("/results?q=Gastroenterologist&loc=Newark%2C+DE+19711"),
    step("/results?q=Gastroenterologist&loc=Newark%2C+DE+19711&page=2"),
    step(profile(SLUG), "done"),
]
ANSWER = "More Than Most: Acid Reflux (GERD). First under View Top 20: Anemia."


def genuine_after() -> State:
    return State()

class VerifyTask5Tests(SharedVerifierTests, VerifierTestCase):
    N = 5
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def genuine_after(self) -> State:
        return genuine_after()


    def test_shortcut_fails_on_gate(self) -> None:
        steps = [step("/"), step("/results?q=Gastroenterologist", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_profile_" + SLUG)

    def test_missing_results_visit_fails(self) -> None:
        steps = [step("/"), step(profile(SLUG), "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_results_gastroenterologist_search")

    def test_listing_all_five_still_passes(self) -> None:
        answer = ("Top five: Celiac Disease, Crohn's Disease, Irritable Bowel Syndrome, Acid Reflux (GERD), Hemorrhoids. "
                  "The one marked More Than Most is GERD; the first Top 20 entry is Anemia.")
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_wrong_answer_0_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'More Than Most: Celiac Disease. First top-20: Anemia.', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_more_than_most_condition')

    def test_wrong_answer_1_fails(self) -> None:
        verdict = self.verdict(GENUINE_STEPS, 'More Than Most: Acid Reflux (GERD). First top-20: Hepatitis C.', after=genuine_after())
        self.assertFailsOn(verdict, 'answer_has_first_top20_condition')

    def test_read_only_write_fails(self) -> None:
        after = genuine_after()
        after.add_saved(2, 106)
        self.assertFailsOn(self.verdict(GENUINE_STEPS, ANSWER, after=after), "read_only_saved_providers_unchanged")


    def test_swapped_condition_roles_fail(self) -> None:
        bad = "More Than Most: Anemia. First under View Top 20: GERD."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, bad), "answer_does_not_swap_condition_roles")

    def test_profile_before_results_fails(self) -> None:
        steps = [step("/"), step(profile(SLUG)), step("/results?q=Gastroenterologist&loc=Newark%2C+DE+19711", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "results_precede_profile")


if __name__ == "__main__":
    unittest.main()
