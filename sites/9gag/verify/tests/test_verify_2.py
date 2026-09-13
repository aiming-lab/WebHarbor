from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import ReadTaskTests, step  # noqa: E402

ORIGINAL = "/gag/solar-powered-camping-setup-survives-a-rainy-weekend-11"


class VerifyTask2Tests(ReadTaskTests):
    N = 2
    GENUINE_STEPS = [step("/"), step("/", "input", "solar camping"), step("/search?q=solar+camping"), step(ORIGINAL, "done")]
    ANSWER = "A 120-watt folding panel; the controller was stored inside a waterproof lunch box."
    FIRST_GATE = "visited_search_results"
    WRONG_ANSWERS = {
        "A 200-watt panel and a waterproof lunch box.": "answer_has_panel_wattage",
        "A 120 W panel; the controller was in a dry bag.": "answer_has_controller_protection",
        "1200 W panel, lunch box.": "answer_has_panel_wattage",
    }

    def test_lunchbox_spelling_variants_pass(self) -> None:
        self.assertPasses(self.verdict(self.GENUINE_STEPS, "120W, waterproof lunchbox"))
        self.assertPasses(self.verdict(self.GENUINE_STEPS, "120 watts; a lunch-box"))


if __name__ == "__main__":
    unittest.main()
