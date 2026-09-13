from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import ReadTaskTests, step  # noqa: E402

ORIGINAL = "/gag/street-musician-turns-a-rain-delay-into-a-concert-22"
REMIX = "/gag/community-remix-12-street-musician-turns-a-rain-delay-into-a-concert-57"


class VerifyTask8Tests(ReadTaskTests):
    N = 8
    GENUINE_STEPS = [step("/"), step("/", "input", "rain delay concert"), step("/search?q=rain+delay+concert"), step(ORIGINAL, "done")]
    ANSWER = "Commuters joined the chorus under platform seven."
    FIRST_GATE = "visited_search_results"
    WRONG_ANSWERS = {
        "Platform six.": "answer_has_platform_number",
        "Platform 17.": "answer_has_platform_number",
    }

    def test_remix_clone_is_accepted(self) -> None:
        """The clone repeats the original's description verbatim, so an agent that reads the facts off
        it has answered the question; failing it would be a hidden provenance rule (verify/README.md)."""
        steps = [step("/"), step("/search?q=concert"), step(REMIX, "done")]
        self.assertPasses(self.verdict(steps, self.ANSWER))

    def test_unrelated_detail_page_still_fails(self) -> None:
        """Mutation proof that widening the gate did not disable it."""
        steps = [step("/"), step("/search?q=concert"),
                 step("/gag/a-fox-naps-on-the-same-garden-wall-every-afternoon-23", "done")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER), "visited_post_detail")

    def test_numeric_platform_passes(self) -> None:
        self.assertPasses(self.verdict(self.GENUINE_STEPS, "Platform 7"))


if __name__ == "__main__":
    unittest.main()
