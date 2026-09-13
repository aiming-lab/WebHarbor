from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import ReadTaskTests, step  # noqa: E402

ORIGINAL = "/gag/a-baker-recreates-a-city-skyline-in-sourdough-16"
REMIX = "/gag/community-remix-6-a-baker-recreates-a-city-skyline-in-sourdough-51"


class VerifyTask6Tests(ReadTaskTests):
    N = 6
    GENUINE_STEPS = [step("/"), step("/", "input", "sourdough skyline"), step("/search?q=sourdough+skyline"), step(ORIGINAL, "done")]
    ANSWER = "The edible skyline took three attempts and nearly fourteen hours to shape."
    FIRST_GATE = "visited_search_results"
    WRONG_ANSWERS = {
        "Two attempts and fourteen hours.": "answer_has_attempt_count",
        "Three attempts and four hours.": "answer_has_shaping_hours",
    }

    def test_remix_clone_is_accepted(self) -> None:
        """The clone repeats the original's description verbatim, so an agent that reads the facts off
        it has answered the question; failing it would be a hidden provenance rule (verify/README.md)."""
        steps = [step("/"), step("/search?q=sourdough"), step(REMIX, "done")]
        self.assertPasses(self.verdict(steps, self.ANSWER))

    def test_unrelated_detail_page_still_fails(self) -> None:
        """Mutation proof that widening the gate did not disable it."""
        steps = [step("/"), step("/search?q=sourdough"),
                 step("/gag/a-fox-naps-on-the-same-garden-wall-every-afternoon-23", "done")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER), "visited_post_detail")

    def test_numeric_forms_pass(self) -> None:
        self.assertPasses(self.verdict(self.GENUINE_STEPS, "3 attempts, ~14 hours"))


if __name__ == "__main__":
    unittest.main()
