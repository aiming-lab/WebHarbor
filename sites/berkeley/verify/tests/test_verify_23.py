from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, step,
)

GENUINE_STEPS = [step("/"), step("/research"), step("/research/bids", "done")]
ANSWER = (
    # The related centre is the first of BIDS's ORDER BY name LIMIT 3 list
    # (app.py research_center; ground_truth.related_centres mirrors it).
    "BIDS is directed by Prof. David Culler; its focus areas are Data Science, Statistics, "
    "Computational Methods and Open Science. A related center listed on the page is the "
    "Berkeley Center for New Media."
)


class VerifyTask23Tests(SharedVerifierTests, VerifierTestCase):
    N = 23
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_shortcut_from_listing_fails(self) -> None:
        steps = [step("/"), step("/research", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_research_detail_bids")

    def test_wrong_director_fails(self) -> None:
        answer = (
            "BIDS is directed by Prof. Douglas Dreger; its focus areas are Data Science, "
            "Statistics, and Computational Methods; a related center is the Berkeley "
            "Seismological Laboratory."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_director")

    def test_invented_focus_areas_fail(self) -> None:
        answer = (
            "BIDS is directed by Prof. David Culler and focuses on Machine Learning, Robotics, "
            "and Climate Policy."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_focus_areas")

    def test_unrendered_related_centre_fails(self) -> None:
        answer = (
            "BIDS is directed by Prof. David Culler; focus areas are Data Science, Statistics "
            "and Computational Methods; a related center on the page is the California Policy Lab."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_names_rendered_related_centre")

    def test_negated_director_fails(self) -> None:
        answer = (
            "Prof. David Culler is not the director of BIDS; its focus areas are Data Science, "
            "Statistics and Computational Methods."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_director")

    def test_negated_director_with_title_fails(self) -> None:
        """C2 regression: "is not directed by Prof. X" — the title's period must
        not hide the negation from the director matcher."""
        answer = (
            "Berkeley Institute for Data Science is not directed by Prof. David Culler; its "
            "focus areas are Data Science, Statistics, Computational Methods, Open Science."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_director")

    def test_alternative_phrasing_passes(self) -> None:
        answer = (
            "The Berkeley Institute for Data Science, led by David Culler, works across Data "
            "Science, Statistics, Computational Methods and Open Science; the Berkeley "
            "Population Center is listed among its related centers."
        )
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "research", 2)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
