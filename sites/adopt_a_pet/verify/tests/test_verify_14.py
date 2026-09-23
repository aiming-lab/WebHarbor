from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import CommonCases, VerifierTestCase, step, without_path  # noqa: E402


class VerifyTask14Tests(CommonCases, VerifierTestCase):
    N = 14
    GENUINE_STEPS = [step("/"), step("/search?location=New+York%2C+NY&species="), step("/pet/luna"), step("/pet/milo", "done")]
    ANSWER = "Luna $250, Milo $150 — Milo is the lower-fee pet."

    def test_missing_profile_fails(self):
        self.assertFailsOn(self.verdict(without_path(self.GENUINE_STEPS, "/pet/milo"), self.ANSWER), "visited_pet_milo")

    def test_wrong_comparison_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Luna $250, Milo $150 — Luna has the lower fee."), "answer_identifies_lower_fee_pet")

    def test_wrong_fee_fails(self):
        self.assertFailsOn(self.verdict(self.GENUINE_STEPS, "Luna $205, Milo $150 — Milo is lower."), "answer_has_both_fees")

    def test_ny_only_query_passes(self):
        self.assertPasses(self.verdict([step("/"), step("/search?location=NY&species="), step("/pet/luna"), step("/pet/milo", "done")], self.ANSWER))


if __name__ == "__main__":
    unittest.main()
