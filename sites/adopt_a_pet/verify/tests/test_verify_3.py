from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, VerifierTestCase, step, without_path  # noqa: E402


class VerifyTask3Tests(CommonCases, VerifierTestCase):
    N = 3
    GENUINE_STEPS = [step("/"), step("/search?location=Arizona&species=Cat"),
                     step("/search?distance=50+miles+or+less&location=Arizona&species=Cat&breed=&sex=&age=Adult&size="),
                     step("/pet/casper"), step("/pet/cinders", "done")]
    ANSWER = "Cinders — Sedona, Domestic Shorthair, $120 (lower than Casper at $125)."

    def test_missing_age_filter_fails(self):
        steps = [step("/"), step("/search?location=Arizona&species=Cat"), step("/pet/casper"), step("/pet/cinders", "done")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER), "visited_adult_cat_search_arizona")

    def test_missing_second_profile_fails(self):
        self.assertFailsOn(self.verdict(without_path(self.GENUINE_STEPS, "/pet/casper"), self.ANSWER), "visited_pet_casper")

    def test_wrong_pet_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Casper — Mesa, Colorpoint Shorthair, $125"), "answer_names_winner")

    def test_misattribution_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Cinders (Sedona, Domestic Shorthair, $120) and Casper ($125); the cheaper one is Casper."),
                           "answer_identifies_lowest_fee_pet")

    def test_phoenix_az_query_also_counts_as_statewide(self):
        steps = [step("/"), step("/search?location=Phoenix%2C+AZ&species=Cat&age=Adult"), step("/pet/casper"), step("/pet/cinders", "done")]
        self.assertPasses(self.verdict(steps, self.ANSWER))


if __name__ == "__main__":
    unittest.main()
