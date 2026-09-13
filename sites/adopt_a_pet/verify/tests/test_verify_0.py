from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, State, VerifierTestCase, step  # noqa: E402


class VerifyTask0Tests(CommonCases, VerifierTestCase):
    N = 0
    GENUINE_STEPS = [step("/"), step("/search?location=Phoenix%2C+AZ&species=Dog"), step("/pet/waymo", "done")]
    ANSWER = "Waymo: American Pit Bull Terrier / Mixed Breed, Adult, Large, adoption fee $225."

    def test_shortcut_without_search_fails(self):
        self.assertFailsOn(self.verdict([step("/"), step("/pet/waymo", "done")], self.ANSWER), "visited_dog_search_near_phoenix")

    def test_shortcut_without_profile_fails(self):
        self.assertFailsOn(self.verdict([step("/"), step("/search?location=Phoenix%2C+AZ&species=Dog", "done")], self.ANSWER), "visited_pet_waymo")

    def test_wrong_fee_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER.replace("$225", "$250")), "answer_has_fee")

    def test_missing_secondary_breed_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Waymo: American Pit Bull Terrier, Adult, Large, $225"), "answer_has_both_breeds")

    def test_read_only_write_fails(self):
        after = State()
        after.add_favorite("alice.j@test.com", "waymo")
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "read_only_favorite_unchanged")


if __name__ == "__main__":
    unittest.main()
