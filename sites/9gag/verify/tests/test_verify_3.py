from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import ReadTaskTests, step  # noqa: E402

ORIGINAL = "/gag/an-engineer-explains-why-this-bridge-hums-in-the-wind-19"


class VerifyTask3Tests(ReadTaskTests):
    N = 3
    GENUINE_STEPS = [step("/"), step("/interest/science"), step("/interest/science?page=2"), step(ORIGINAL, "done")]
    ANSWER = "The note is near 440 hertz and is produced by evenly spaced railings."
    FIRST_GATE = "visited_science_interest_feed"
    WRONG_ANSWERS = {
        "About 44 Hz from the railings.": "answer_has_frequency_hertz",
        "440 Hz produced by the cables.": "answer_has_resonating_feature",
    }

    def test_search_instead_of_browse_fails(self) -> None:
        steps = [step("/"), step("/search?q=bridge"), step(ORIGINAL, "done")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER), "visited_science_interest_feed")


if __name__ == "__main__":
    unittest.main()
