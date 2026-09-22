from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, VerifierTestCase, step  # noqa: E402


class VerifyTask10Tests(CommonCases, VerifierTestCase):
    N = 10
    GENUINE_STEPS = [step("/"), step("/shelters"), step("/shelters?q=Seattle"), step("/shelter/4", "done")]
    ANSWER = "Pacific Animal Haven — 206-555-0119 — info@pacifichaven.test — pets: Daisy and Pepper."

    def test_no_shelter_search_fails(self):
        self.assertFailsOn(self.verdict([step("/"), step("/shelters"), step("/shelter/4", "done")], self.ANSWER), "used_shelter_search_for_seattle")

    def test_no_shelter_page_fails(self):
        self.assertFailsOn(self.verdict([step("/"), step("/shelters?q=Seattle", "done")], self.ANSWER), "visited_shelter_4")

    def test_missing_pet_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Pacific Animal Haven, 206-555-0119, info@pacifichaven.test, pets: Daisy."), "answer_lists_every_pet")

    def test_wrong_email_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Pacific Animal Haven, 206-555-0119, info@pacific.test, Daisy, Pepper"), "answer_has_email")


if __name__ == "__main__":
    unittest.main()
