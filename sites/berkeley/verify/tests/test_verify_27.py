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
    step("/programs?q=Master%20of%20Engineering"),
    step("/programs/master-of-engineering-meng"),
    step("/programs/computer-science-ms", "done"),
]
ANSWER = (
    "The Master of Engineering is offered by the Department of Electrical Engineering and "
    "Computer Sciences (EECS). The MEng takes 1 year, while the Computer Science MS takes 1.5 "
    "years."
)


class VerifyTask27Tests(SharedVerifierTests, VerifierTestCase):
    N = 27
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_degree_filter_also_satisfies_search_gate(self) -> None:
        steps = [step("/"), step("/programs?degree=MEng"),
                 step("/programs/master-of-engineering-meng"),
                 step("/programs/computer-science-ms", "done")]
        self.assertPasses(self.verdict(steps, ANSWER))

    def test_site_search_route_also_satisfies_search_gate(self) -> None:
        """§0.4 loosening: the ques says "Search the Berkeley site for …", so the site search counts."""
        steps = [step("/"), step("/search?q=Master+of+Engineering"),
                 step("/programs/master-of-engineering-meng"),
                 step("/programs/computer-science-ms", "done")]
        self.assertPasses(self.verdict(steps, ANSWER))

    def test_catalog_wide_search_still_fails_search_gate(self) -> None:
        """The loosening must not admit a search that does not name the MEng term."""
        steps = [step("/"), step("/search?q=california"),
                 step("/programs/master-of-engineering-meng"),
                 step("/programs/computer-science-ms", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_program_search")

    def test_site_search_alone_without_detail_pages_still_fails(self) -> None:
        """The detail gates, not the search gate, stay the binding anti-shortcut anchors."""
        steps = [step("/"), step("/search?q=Master+of+Engineering", "done")]
        self.assertFailsOn(
            self.verdict(steps, ANSWER), "visited_program_detail_master-of-engineering-meng"
        )

    def test_missing_ms_hop_fails(self) -> None:
        steps = [
            step("/"), step("/programs?q=Master%20of%20Engineering"),
            step("/programs/master-of-engineering-meng", "done"),
        ]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_program_detail_computer-science-ms")

    def test_missing_meng_hop_fails(self) -> None:
        steps = [
            step("/"), step("/programs?q=Master%20of%20Engineering"),
            step("/programs/computer-science-ms", "done"),
        ]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_program_detail_master-of-engineering-meng")

    def test_no_listing_at_all_fails_search_gate(self) -> None:
        steps = [step("/"), step("/programs/computer-science-ms", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_program_search")

    def test_swapped_or_wrong_durations_fail(self) -> None:
        answer = (
            "The Master of Engineering is offered by EECS and takes 2 years; the Computer Science "
            "MS takes 2 years."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_meng_duration")

    def test_wrong_ms_duration_fails(self) -> None:
        answer = (
            "The Master of Engineering is offered by EECS and takes 1 year, while the Computer "
            "Science MS takes 2 years."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_ms_duration")

    def test_negated_duration_fails(self) -> None:
        answer = (
            "The Master of Engineering, offered by EECS, is not a 1-year program; the Computer "
            "Science MS takes 1.5 years."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_meng_duration")

    def test_alternative_phrasing_passes(self) -> None:
        answer = (
            "The Master of Engineering in EECS lasts one year, while the Computer Science MS "
            "lasts 1.5 years."
        )
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "program", 43)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
