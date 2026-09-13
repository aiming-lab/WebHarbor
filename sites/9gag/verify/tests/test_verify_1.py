from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import ReadTaskTests, step  # noqa: E402

ORIGINAL = "/gag/rescue-cat-learns-the-sound-of-the-treat-drawer-13"


class VerifyTask1Tests(ReadTaskTests):
    N = 1
    GENUINE_STEPS = [step("/"), step("/", "input", "rescue cat"), step("/search?q=rescue+cat"), step(ORIGINAL, "done")]
    ANSWER = "Miso arrived at Harbor Paws in February and learned the routine after eleven days."
    FIRST_GATE = "visited_search_results"
    WRONG_ANSWERS = {
        "Miso arrived in March and learned it in eleven days.": "answer_has_arrival_month",
        "Miso arrived in February and learned it in 12 days.": "answer_has_days_count",
        "February; it took 110 days.": "answer_has_days_count",
    }

    def test_numeric_days_pass(self) -> None:
        self.assertPasses(self.verdict(self.GENUINE_STEPS, "February, 11 days"))


if __name__ == "__main__":
    unittest.main()
