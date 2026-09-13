from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, State, VerifierTestCase, step  # noqa: E402


class VerifyTask1Tests(CommonCases, VerifierTestCase):
    N = 1
    GENUINE_STEPS = [step("/"), step("/search?location=Scottsdale%2C+AZ&species=Cat"), step("/pet/neo", "done")]
    ANSWER = "Neo, 7 months old, Black, good with children: Yes."

    def test_shortcut_fails(self):
        self.assertFailsOn(self.verdict([step("/"), step("/pet/neo", "done")], self.ANSWER), "visited_cat_search_near_scottsdale")

    def test_other_kitten_fails(self):
        steps = [step("/"), step("/search?location=Scottsdale%2C+AZ&species=Cat"), step("/pet/amba", "done")]
        self.assertFailsOn(self.verdict(steps, "Amba, 5 months, Tabby, good with children: Yes"), "visited_pet_neo")

    def test_wrong_children_flag_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Neo, 7 months, Black, not good with children"), "answer_states_good_with_children_yes")

    def test_age_group_instead_of_months_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Neo, Kitten, Black, good with children: yes"), "answer_has_age_months")

    def test_read_only_write_fails(self):
        after = State()
        after.add_alert("alice.j@test.com", "Cat", "", "85250", 10)
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, self.ANSWER, after=after), "read_only_pet_alert_unchanged")


if __name__ == "__main__":
    unittest.main()
