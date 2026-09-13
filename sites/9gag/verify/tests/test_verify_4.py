from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import ReadTaskTests, step  # noqa: E402

ORIGINAL = "/gag/neighborhood-builds-a-miniature-library-for-night-shift-workers-18"


class VerifyTask4Tests(ReadTaskTests):
    N = 4
    GENUINE_STEPS = [step("/"), step("/", "input", "community library"), step("/search?q=community+library"), step(ORIGINAL, "done")]
    ANSWER = "The cabinet is blue and it is restocked every Thursday at 6 a.m. by local volunteers."
    FIRST_GATE = "visited_search_results"
    WRONG_ANSWERS = {
        "Red cabinet, restocked Thursdays at 6 a.m.": "answer_has_cabinet_colour",
        "Blue cabinet, restocked Fridays at 6 a.m.": "answer_has_restock_day",
        "Blue cabinet, restocked Thursday at 6 p.m.": "answer_has_restock_time",
    }

    def test_time_variants_pass(self) -> None:
        self.assertPasses(self.verdict(self.GENUINE_STEPS, "blue; every Thursday at 06:00"))
        self.assertPasses(self.verdict(self.GENUINE_STEPS, "Blue - Thursday 6AM"))


if __name__ == "__main__":
    unittest.main()
