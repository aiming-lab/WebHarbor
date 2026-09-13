from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import ReadTaskTests, step  # noqa: E402

ORIGINAL = "/gag/tiny-lighthouse-office-with-the-best-ocean-view-12"
REMIX = "/gag/community-remix-2-tiny-lighthouse-office-with-the-best-ocean-view-47"


class VerifyTask0Tests(ReadTaskTests):
    N = 0
    GENUINE_STEPS = [step("/"), step("/", "input", "lighthouse offices"), step("/search?q=lighthouse+offices"), step(ORIGINAL, "done")]
    ANSWER = "The circular room is 4.2 meters wide and the desk was built from reclaimed oak."
    FIRST_GATE = "visited_search_results"
    WRONG_ANSWERS = {
        "The room is 4.25 meters wide and the desk is reclaimed oak.": "answer_has_room_width_meters",
        "The room is 4.2 meters wide and the desk is walnut.": "answer_has_desk_material",
        "The room is 4.2 meters wide; the desk is not reclaimed oak.": "answer_has_desk_material",
    }

    def test_remix_clone_detail_also_counts(self) -> None:
        steps = [step("/"), step("/search?q=lighthouse"), step(REMIX, "done")]
        self.assertPasses(self.verdict(steps, "4.2 m wide, reclaimed oak desk"))

    def test_search_without_related_token_fails(self) -> None:
        steps = [step("/"), step("/search?q=cats"), step(ORIGINAL, "done")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER), "visited_search_results")

    def test_results_page_only_fails(self) -> None:
        steps = [step("/"), step("/search?q=lighthouse+offices", "done")]
        self.assertFailsOn(self.verdict(steps, self.ANSWER), "visited_post_detail")


if __name__ == "__main__":
    unittest.main()
