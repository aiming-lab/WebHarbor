from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, VerifierTestCase, step, without_path  # noqa: E402

FILTERED = "/search?distance=50+miles+or+less&location=Arizona&species=Dog&breed=&sex=&age=&size=Small"


class VerifyTask12Tests(CommonCases, VerifierTestCase):
    N = 12
    GENUINE_STEPS = [step("/"), step("/search?location=Arizona&species=Dog"), step(FILTERED),
                     step("/pet/batman"), step("/pet/sirius"), step("/pet/winston"), step("/pet/yuki"), step("/pet/zorro", "done")]
    ANSWER = "Youngest: Batman, 36 months, Chihuahua / Yorkshire Terrier, Tucson."

    def test_adults_only_passes(self):
        self.assertPasses(self.verdict(without_path(self.GENUINE_STEPS, "/pet/sirius", "/pet/yuki"), self.ANSWER))

    def test_missing_adult_profile_fails(self):
        self.assertFailsOn(self.verdict(without_path(self.GENUINE_STEPS, "/pet/winston"), self.ANSWER), "visited_pet_winston")

    def test_no_size_filter_fails(self):
        steps = [step("/"), step("/search?location=Arizona&species=Dog"), step("/pet/batman"), step("/pet/winston"), step("/pet/zorro", "done")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER), "visited_small_dog_search_arizona")

    def test_wrong_pet_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Youngest: Winston, 60 months, Chihuahua / Mixed Breed, Tempe."), "answer_names_winner")

    def test_misattribution_fails(self):
        answer = "Batman (Chihuahua / Yorkshire Terrier, Tucson) 36 months, Winston 60 months, Zorro 72 months. The youngest is Zorro."
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, answer), "answer_identifies_youngest")


if __name__ == "__main__":
    unittest.main()
