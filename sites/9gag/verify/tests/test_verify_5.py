from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import ReadTaskTests, step  # noqa: E402

ORIGINAL = "/gag/grandmother-finishes-her-first-marathon-at-seventy-two-15"


class VerifyTask5Tests(ReadTaskTests):
    N = 5
    GENUINE_STEPS = [step("/"), step("/interest/sports"), step(ORIGINAL, "done")]
    ANSWER = "Her family met her at kilometer 38 with handmade orange flags."
    FIRST_GATE = "visited_sports_interest_feed"
    WRONG_ANSWERS = {
        "At kilometer 28 with orange flags.": "answer_has_kilometre",
        "At kilometer 38 with red flags.": "answer_has_flag_colour",
        "Kilometer 380, orange.": "answer_has_kilometre",
    }


if __name__ == "__main__":
    unittest.main()
