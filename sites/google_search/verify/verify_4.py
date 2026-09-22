#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--4.

Show most played games in Steam. And tell me the number of players in In game at this time

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Steam charts page lists the most played game as
    Counter-Strike 2 with 938,210 current concurrent players; SteamDB and
    SteamCharts show the same 938,210 figure. (Epic/Polygon/GameSpot pages are
    distractors.)
Source pages: store.steampowered.com/charts/mostplayed, steamdb.info/charts, steamcharts.com/top

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Steam games search | a Steam charts page opened | answer: the most
  played game and its current player count
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, Judge, parse_args, searched_all_tokens,
                        visited_any_page, navigated_to, contains_all, contains_any,
                        re_any, re_count, number_claim, date_in, name_in, count_names,
                        order_by_first_mention)


def main():
    a = parse_args()
    j = Judge('Google Search--4', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["steam", "games"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-004-", "charts/mostplayed", "steamdb", "steamcharts"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_most_played_game", contains_any(fa, ["counter-strike 2", "counter strike 2", "cs2"]),
            f"final={fa[:200]!r}")
    j.check("answer_player_count", number_claim(fa, 938210),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
