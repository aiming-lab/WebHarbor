from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, VerifierTestCase, step  # noqa: E402


class VerifyTask11Tests(CommonCases, VerifierTestCase):
    N = 11
    GENUINE_STEPS = [step("/"), step("/breeds"), step("/search?breed=Maine+Coon&species=Cat"), step("/pet/milo", "done")]
    ANSWER = "Milo, Male, New York, NY, adoption fee $150."

    def test_no_breed_page_fails(self):
        self.assertFailsOn(self.verdict([step("/"), step("/search?breed=Maine+Coon&species=Cat"), step("/pet/milo", "done")], self.ANSWER), "visited_breed_101")

    def test_no_profile_fails(self):
        self.assertFailsOn(self.verdict([step("/"), step("/breeds"), step("/search?breed=Maine+Coon&species=Cat", "done")], self.ANSWER), "visited_pet_milo")

    def test_wrong_fee_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Milo, Male, New York, $250"), "answer_has_fee")

    def test_wrong_sex_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Milo, Female, New York, $150"), "answer_has_sex")


if __name__ == "__main__":
    unittest.main()
