from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, step,
)

SLUG = "crispr-pioneer-jennifer-doudna-receives-national-medal-of-science"
GENUINE_STEPS = [step("/"), step("/news?q=CRISPR"), step(f"/news/{SLUG}", "done")]
ANSWER = "The article features Jennifer Doudna, who received the National Medal of Science."


class VerifyTask4Tests(SharedVerifierTests, VerifierTestCase):
    N = 4
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_shortcut_without_article_fails_on_gate(self) -> None:
        steps = [step("/"), step("/news?q=CRISPR", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), f"visited_news_detail_{SLUG}")

    def test_shortcut_from_research_category_still_needs_article(self) -> None:
        steps = [step("/"), step("/news?category=Research", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), f"visited_news_detail_{SLUG}")

    def test_nobel_prize_answer_fails(self) -> None:
        answer = "The featured scientist is Jennifer Doudna, who received the Nobel Prize."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_award")

    def test_negated_award_fails(self) -> None:
        answer = (
            "Jennifer Doudna is the featured scientist, but the National Medal of Science was "
            "not the award she received; she won the Nobel Prize."
        )
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_award")

    def test_negated_everything_fails_on_first_check(self) -> None:
        answer = "Jennifer Doudna did not receive the National Medal of Science."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_has_scientist")

    def test_wrong_article_covid_fails(self) -> None:
        covid = "berkeley-researchers-develop-faster-covid-test-using-crispr"
        steps = [step("/"), step("/news?q=CRISPR"), step(f"/news/{covid}", "done")]
        answer = "The article is about a faster COVID test using CRISPR; 98% sensitivity."
        self.assertFailsOn(self.verdict(steps, answer), f"visited_news_detail_{SLUG}")

    def test_alternative_phrasing_passes(self) -> None:
        answer = "That story is about Prof. Jennifer Doudna; the award she received was the National Medal of Science."
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "news", 4)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
