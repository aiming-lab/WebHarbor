#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--26.

Find information on ESPN NBA schedule. Tell me yesterday's matchups in which
the loser high was higher than the winner high.

Ground truth (hardcoded; frozen from the served pages — mirror "today" is
April 10, 2024, so yesterday = April 9, 2024 with eight NBA games; comparing
each game's winner-high vs loser-high (from the scoreboard cards / box
scores), exactly ONE matchup qualifies):
    Knicks 102 @ Heat 108: the losing Knicks' high scorer Jalen Brunson (36)
    outscored the winning Heat's high scorer Jimmy Butler (27).
    All other April 9 games have the winner's high above the loser's high.

Checks: run-package gate + answer + navigation (scoreboard/schedule/game) +
the Knicks-Heat matchup with 36 and 27 + Brunson or Butler named + read-only
DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        num_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--26', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_scores_pages",
            navigated_any(t, ["/nba/scoreboard", "/nba/schedule", "/scores", "/game/"]),
            "must open the NBA scoreboard/schedule, all-scores, or a game page")
    j.check("answer_qualifying_matchup",
            contains_any(fa, ["knick", "new york"]) and
            contains_any(fa, ["heat", "miami"]),
            "the only qualifying matchup: Knicks @ Heat (Apr 9, 2024)")
    j.check("answer_highs_36_27", num_in(fa, 36) and num_in(fa, 27),
            "loser high Brunson 36 > winner high Butler 27")
    j.check("answer_named_player",
            contains_any(fa, ["brunson"]) or contains_any(fa, ["butler"]),
            "the high scorers must be named (Brunson / Butler)")
    j.emit()

if __name__ == "__main__":
    main()
