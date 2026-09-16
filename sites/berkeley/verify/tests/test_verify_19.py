from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import (  # noqa: E402,F401
    SharedVerifierTests, State, VerifierTestCase, step,
)

GYM = "/news/womens-gymnastics-wins-ncaa-championship"
MEDALS = "/news/berkeley-athletes-win-record-12-medals-at-winter-world-university-games"
GENUINE_STEPS = [step("/"), step("/news?category=Athletics"), step(GYM, "done")]
ANSWER = (
    "Women's Gymnastics won the NCAA Championship, led by an all-around champion and three "
    "perfect 10.0 scores on the balance beam."
)


class VerifyTask19Tests(SharedVerifierTests, VerifierTestCase):
    N = 19
    GENUINE_STEPS = GENUINE_STEPS
    ANSWER = ANSWER

    def test_genuine_run_passes(self) -> None:
        self.assertPasses(self.verdict(GENUINE_STEPS, ANSWER))

    def test_shortcut_without_article_fails(self) -> None:
        steps = [step("/"), step("/news?category=Athletics", "done")]
        self.assertFailsOn(self.verdict(steps, ANSWER), "visited_championship_article")

    def test_non_championship_article_fails(self) -> None:
        steps = [step("/"), step("/news?category=Athletics"), step(MEDALS, "done")]
        answer = "Berkeley athletes won a record 12 medals at the Winter World University Games."
        self.assertFailsOn(self.verdict(steps, answer), "visited_championship_article")

    def test_swimming_championship_also_passes(self) -> None:
        steps = [
            step("/"),
            step("/news?category=Athletics"),
            step("/news/cal-wins-pac-12-swimming-and-diving-championship", "done"),
        ]
        answer = "Cal won the Pac-12 Swimming and Diving Championship with 1,400 points."
        self.assertPasses(self.verdict(steps, answer))

    def test_wrong_sport_for_visited_article_fails(self) -> None:
        answer = "Cal won the Pac-12 football championship."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_binds_to_championship_article")

    def test_negated_championship_fails(self) -> None:
        answer = "Women's Gymnastics did not win the NCAA Championship."
        self.assertFailsOn(self.verdict(GENUINE_STEPS, answer), "answer_binds_to_championship_article")

    def test_alternative_phrasing_passes(self) -> None:
        answer = (
            "The NCAA championship was won by the women's gymnastics team, which scored three "
            "perfect 10.0s on the balance beam."
        )
        self.assertPasses(self.verdict(GENUINE_STEPS, answer))

    def test_read_only_write_fails(self) -> None:
        after = State()
        after.add_bookmark(1, "news", 19)
        verdict = self.verdict(GENUINE_STEPS, ANSWER, after=after)
        self.assertFailsOn(verdict, "read_only_bookmarks_unchanged")


if __name__ == "__main__":
    unittest.main()
