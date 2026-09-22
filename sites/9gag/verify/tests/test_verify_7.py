from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import ReadTaskTests, step  # noqa: E402

ORIGINAL = "/gag/mechanical-keyboard-made-entirely-from-transparent-parts-14"


class VerifyTask7Tests(ReadTaskTests):
    N = 7
    GENUINE_STEPS = [step("/"), step("/interest/gaming"), step(ORIGINAL, "done")]
    ANSWER = "It uses silent tactile switches and a hand-polished acrylic case."
    FIRST_GATE = "visited_gaming_interest_feed"
    WRONG_ANSWERS = {
        "Clicky switches and an acrylic case.": "answer_has_switch_type",
        "Silent tactile switches and an aluminium case.": "answer_has_case_material",
    }


if __name__ == "__main__":
    unittest.main()
