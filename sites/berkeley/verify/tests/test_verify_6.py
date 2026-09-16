from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, step,
)

GENUINE_STEPS = [
    step("/"),
    step("/events?category=Lecture"),
    step("/events/1"),
    step("/events/31"),
    step("/events/51", "done"),
]
ANSWER = (
    "Lecture events: 'Nobel Laureate Lecture: Jennifer Doudna on the Future of Gene Editing' "
    "on May 15, 2026 at 2050 Valley Life Sciences Building; 'Public Lecture: The Future of "
    "Democracy in the Digital Age' on May 21, 2026 at 145 Dwinelle Hall; and 'Berkeley Science "
    "Lecture: Origins of Life' on May 19, 2026 at 1 Pimentel Hall."
)


class VerifyTask6Tests(SharedVerifierTests, VerifierTestCase):
    N = 6
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_date_all_listing_also_satisfies_gate(self) -> None:
        steps = [step("/"), step("/events?category=Lecture&date=all"),
                 step("/events/1"), step("/events/31"), step("/events/51", "done")]
        self.assertPasses(self.verdict(steps, ANSWER))

    def test_catalog_wide_search_does_not_satisfy_listing_gate(self) -> None:
        steps = [step("/"), step("/events?q=lecture", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_lecture_listing")

    def test_other_category_events_fail(self) -> None:
        answer = (
            "Events: 'Spring Career Fair 2026' on May 17, 2026 at Recreational Sports Facility; "
            "'Hackathon: Code for Climate 2026' on May 30, 2026 at Soda Hall; and 'Berkeley "
            "Startup Pitch Competition Finals' on June 4, 2026 at 310 Sutardja Dai Hall."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_lists_three_lecture_events")

    def test_two_events_only_fails(self) -> None:
        answer = (
            "Lecture events: 'Nobel Laureate Lecture: Jennifer Doudna on the Future of Gene "
            "Editing' on May 15, 2026 at 2050 Valley Life Sciences Building, and 'Public Lecture: "
            "The Future of Democracy in the Digital Age' on May 21, 2026 at 145 Dwinelle Hall."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_lists_three_lecture_events")

    def test_wrong_date_fails(self) -> None:
        answer = ANSWER.replace("May 15, 2026", "May 16, 2026").replace("May 21, 2026", "May 22, 2026").replace("May 19, 2026", "May 20, 2026")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_lists_three_lecture_events")

    def test_negated_listing_fails(self) -> None:
        answer = "There are no Lecture events I could list."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_lists_three_lecture_events")

    def test_alternative_phrasing_passes(self) -> None:
        answer = (
            "Lecture events: 'Nobel Laureate Lecture: Jennifer Doudna on the Future of Gene "
            "Editing' 2026-05-15, 2050 Valley Life Sciences Building; 'Public Lecture: The Future "
            "of Democracy in the Digital Age' 2026-05-21, 145 Dwinelle Hall; 'Berkeley Science "
            "Lecture: Origins of Life' 2026-05-19, 1 Pimentel Hall."
        )
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "event", 1)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
