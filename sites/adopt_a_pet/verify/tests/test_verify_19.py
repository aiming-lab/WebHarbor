from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, VerifierTestCase, step, without_path  # noqa: E402

SEARCH = "/search?location=Arizona&species=Dog"


class VerifyTask19Tests(CommonCases, VerifierTestCase):
    N = 19
    GENUINE_STEPS = [step("/"), step(SEARCH), step("/pet/arno"), step("/pet/batman"), step("/pet/horus"), step("/pet/sirius"),
                     step("/pet/waymo"), step("/pet/winston"), step(SEARCH + "&page=2"), step("/pet/yuki"), step("/pet/zorro", "done")]
    ANSWER = "Arno — Casa Grande, AZ — German Shepherd Dog / Mixed Breed — 43 months — $200 (lowest fee among the dogs good with children)."

    def test_missing_page_2_fails(self):
        self.assertFailsOn(self.verdict([s for s in self.GENUINE_STEPS if "page=2" not in s["url"]], self.ANSWER), "visited_results_page_2")

    def test_missing_profile_fails(self):
        self.assertFailsOn(self.verdict(without_path(self.GENUINE_STEPS, "/pet/yuki"), self.ANSWER), "visited_pet_yuki")

    def test_wrong_pet_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Batman — Tucson — Chihuahua / Yorkshire Terrier — 36 months — $165"), "answer_names_winner")

    def test_misattribution_fails(self):
        answer = "Arno (Casa Grande, German Shepherd Dog / Mixed Breed, 43 months, $200), Horus $210, Waymo $225, Yuki $205: the lowest fee is Yuki."
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, answer), "answer_identifies_lowest_fee_pet")

    def test_phoenix_az_query_passes(self):
        steps = [s.copy() for s in self.GENUINE_STEPS]
        for s in steps:
            s["url"] = s["url"].replace("location=Arizona", "location=Phoenix%2C+AZ")
        self.assertPasses(self.verdict(steps, self.ANSWER))


if __name__ == "__main__":
    unittest.main()
