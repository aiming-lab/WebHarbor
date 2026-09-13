from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, VerifierTestCase, step  # noqa: E402


class VerifyTask18Tests(CommonCases, VerifierTestCase):
    N = 18
    GENUINE_STEPS = [step("/"), step("/blog", "done")]
    ANSWER = ('Titles: "What to know about pet adoption paperwork", "Why is there an adoption fee?", '
              '"Bringing home your newly adopted dog".')

    def test_no_blog_visit_fails(self):
        self.assertFailsOn(self.verdict([step("/", "done")], self.ANSWER), "visited_pet_advice")

    def test_paraphrased_title_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, 'What to know about pet adoption paperwork; Why are there adoption fees?; Bringing home your newly adopted dog'),
                           "answer_has_title_1")

    def test_missing_title_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, 'What to know about pet adoption paperwork; Why is there an adoption fee?'), "answer_has_title_2")


if __name__ == "__main__":
    unittest.main()
