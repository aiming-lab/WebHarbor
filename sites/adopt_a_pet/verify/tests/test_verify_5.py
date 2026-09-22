from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, VerifierTestCase, step, without_path  # noqa: E402


class VerifyTask5Tests(CommonCases, VerifierTestCase):
    N = 5
    GENUINE_STEPS = [step("/"), step("/search?location=Seattle%2C+WA&species="), step("/pet/daisy"), step("/pet/pepper", "done")]
    ANSWER = "Daisy: dog, 30 months, $275. Pepper: cat, 13 months, $130. Pepper has the lower fee."

    def test_missing_profile_fails(self):
        self.assertFailsOn(self.verdict(without_path(self.GENUINE_STEPS, "/pet/daisy"), self.ANSWER), "visited_pet_daisy")

    def test_no_comparison_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Daisy: dog, 30 months, $275. Pepper: cat, 13 months, $130."), "answer_identifies_lower_fee_pet")

    def test_wrong_comparison_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Daisy: dog, 30 months, $275. Pepper: cat, 13 months, $130. Daisy is the lower-fee pet."),
                           "answer_identifies_lower_fee_pet")

    def test_wrong_age_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER.replace("13 months", "3 months")), "answer_has_both_ages")

    def test_inverse_phrasing_passes(self):
        self.assertPasses(self.verdict(self.GENUINE_STEPS, "Daisy (dog, 30 months, $275) is more expensive than Pepper (cat, 13 months, $130)."))


if __name__ == "__main__":
    unittest.main()
