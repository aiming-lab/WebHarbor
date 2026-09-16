from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, step,
)

GENUINE_STEPS = [step("/"), step("/events?category=Career"), step("/events/2", "done")]
ANSWER = (
    "The Spring Career Fair 2026 is on May 17, 2026 at the Recreational Sports Facility, and "
    "registration is required. Two other career events: the Health Sciences Information Fair on "
    "May 15, 2026 at 50 Warren Hall, and the Graduate School Information Fair on May 26, 2026 at "
    "Pauley Ballroom, MLK Student Union."
)


class VerifyTask25Tests(SharedVerifierTests, VerifierTestCase):
    N = 25
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_shortcut_without_detail_fails(self) -> None:
        steps = [step("/"), step("/events?category=Career", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_event_detail_2")

    def test_unfiltered_events_listing_fails(self) -> None:
        steps = [step("/"), step("/events"), step("/events/2", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_career_events_listing")

    def test_wrong_venue_fails(self) -> None:
        answer = ANSWER.replace("Recreational Sports Facility", "Pauley Ballroom")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_anchor_location")

    def test_registration_not_required_fails(self) -> None:
        answer = ANSWER.replace("registration is required", "registration is not required")
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_registration_required")

    def test_only_one_other_event_fails(self) -> None:
        answer = (
            "The Spring Career Fair 2026 is on May 17, 2026 at the Recreational Sports Facility, "
            "registration required. Also the Health Sciences Information Fair on May 15, 2026 at "
            "50 Warren Hall."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_lists_two_other_career_events")

    def test_negated_anchor_fails(self) -> None:
        answer = "The Spring Career Fair is not on May 17, 2026."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_anchor_date")

    def test_alternative_phrasing_passes(self) -> None:
        answer = (
            "Spring Career Fair 2026 — 2026-05-17, Recreational Sports Facility, registration "
            "required. Other career events: Graduate School Information Fair (2026-05-26, Pauley "
            "Ballroom, MLK Student Union) and Health Sciences Information Fair (2026-05-15, 50 "
            "Warren Hall)."
        )
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "event", 2)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
