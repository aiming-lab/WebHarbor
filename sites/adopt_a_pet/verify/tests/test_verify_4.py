from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, VerifierTestCase, step, without_path  # noqa: E402


class VerifyTask4Tests(CommonCases, VerifierTestCase):
    N = 4
    GENUINE_STEPS = [step("/"), step("/search?location=Arizona&species=Dog&breed=German+Shepherd"), step("/pet/arno"), step("/shelter/1", "done")]
    ANSWER = "Desert Paws Rescue, phone 602-555-0141, email hello@desertpaws.test."

    def test_no_search_fails(self):
        self.assertFailsOn(self.verdict([step("/"), step("/pet/arno"), step("/shelter/1", "done")], self.ANSWER), "used_pet_search")

    def test_no_shelter_page_fails(self):
        self.assertFailsOn(self.verdict(without_path(self.GENUINE_STEPS, "/shelter/1") + [step("/pet/arno", "done")], self.ANSWER), "visited_shelter_1")

    def test_wrong_shelter_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Happy Tails Alliance, 480-555-0128, adopt@happytails.test"), "answer_has_rescue_name")

    def test_wrong_phone_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Desert Paws Rescue, 602-555-0114, hello@desertpaws.test"), "answer_has_rescue_phone")

    def test_phone_formats_accepted(self):
        self.assertPasses(self.verdict(self.GENUINE_STEPS, "Desert Paws Rescue / (602) 555-0141 / hello@desertpaws.test"))


if __name__ == "__main__":
    unittest.main()
