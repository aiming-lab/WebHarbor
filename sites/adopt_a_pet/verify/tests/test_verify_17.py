from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, VerifierTestCase, step  # noqa: E402


class VerifyTask17Tests(CommonCases, VerifierTestCase):
    N = 17
    GENUINE_STEPS = [step("/"), step("/search?location=Miami%2C+FL&species=Dog"),
                     step("/search?distance=50+miles+or+less&location=Miami%2C+FL&species=Dog&breed=&sex=&age=Senior&size="),
                     step("/pet/teddy", "done")]
    ANSWER = "Teddy: 96 months old, Poodle / Mixed Breed, $185, house-trained: Yes."

    def test_no_age_filter_fails(self):
        steps = [step("/"), step("/search?location=Miami%2C+FL&species=Dog"), step("/pet/teddy", "done")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER), "visited_senior_dog_search_miami")

    def test_wrong_house_trained_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Teddy: 96 months, Poodle / Mixed Breed, $185, not house-trained."), "answer_states_house_trained_yes")

    def test_missing_months_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Teddy: Senior, Poodle / Mixed Breed, $185, house-trained: Yes."), "answer_has_age_months")

    def test_prose_passes(self):
        self.assertPasses(self.verdict(self.GENUINE_STEPS, "Teddy is a 96-month-old Poodle / Mixed Breed with a $185 fee and he is housebroken."))


if __name__ == "__main__":
    unittest.main()
