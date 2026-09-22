from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, VerifierTestCase, step  # noqa: E402


class VerifyTask13Tests(CommonCases, VerifierTestCase):
    N = 13
    GENUINE_STEPS = [step("/"), step("/search?location=Austin%2C+TX&species=Dog"),
                     step("/search?distance=50+miles+or+less&location=Austin%2C+TX&species=Dog&breed=&sex=Female&age=Adult&size="),
                     step("/pet/ruby", "done")]
    ANSWER = "Ruby: adoption fee $215; good with cats: No; good with children: No."

    def test_no_sex_filter_fails(self):
        steps = [step("/"), step("/search?location=Austin%2C+TX&species=Dog"), step("/pet/ruby", "done")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER), "visited_female_dog_search_austin")

    def test_wrong_cats_flag_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Ruby: $215; good with cats: Yes; good with children: No."), "answer_states_good_with_cats_no")

    def test_wrong_children_flag_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Ruby: $215; good with cats: No; good with children: Yes."), "answer_states_good_with_children_no")

    def test_prose_negation_passes(self):
        self.assertPasses(self.verdict(self.GENUINE_STEPS, "Ruby's fee is $215 and she is not good with cats or children."))

    def test_missing_flags_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Ruby, $215."), "answer_states_good_with_cats_no")


if __name__ == "__main__":
    unittest.main()
