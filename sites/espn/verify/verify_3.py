#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--3.

Retrieve the final score from the most recent NBA game broadcast on ESPN,
including the playing teams' names and the date of the match.

Ground truth (hardcoded; frozen from the served mirror pages — mirror "today"
is April 10, 2024; the most recent finalized NBA games are all from April 9,
2024, and every one of them except Warriors@Nuggets (TNT) was broadcast on
ESPN).  Accepted games (away score first, as shown on /nba/scoreboard):
    Pacers 114 @ Bucks 119 (ESPN), Knicks 102 @ Heat 108 (ESPN),
    Mavericks 110 @ Suns 128 (ESPN), 76ers 110 @ Celtics 118 (ESPN),
    Timberwolves 115 @ Thunder 121 (ESPN), Hawks 118 @ Cavaliers 125 (ESPN),
    Kings 108 @ Pelicans 116 (ESPN).  Date: April 9, 2024.

Checks: run-package gate + answer + navigation (scoreboard / schedule / game
detail) + one accepted April 9 ESPN game with teams, final score, and the
April 9 date + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        game_score_in, norm, Judge, parse_args)

APR9_ESPN_GAMES = [
    (["pacer", "indiana"], ["buck", "milwaukee"], 114, 119),
    (["knick", "new york"], ["heat", "miami"], 102, 108),
    (["maverick", "dallas"], ["sun", "phoenix"], 110, 128),
    (["76er", "philadelphia", "sixers"], ["celtic", "boston"], 110, 118),
    (["timberwolve", "wolves", "minnesota"], ["thunder", "okc", "oklahoma city"], 115, 121),
    (["hawk", "atlanta"], ["cavalier", "cleveland"], 118, 125),
    (["king", "sacramento"], ["pelican", "new orleans"], 108, 116),
]

def main():
    a = parse_args()
    j = Judge('ESPN--3', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_scores_pages",
            navigated_any(t, ["/nba/scoreboard", "/nba/schedule", "/scores", "/game/"]),
            "must open the NBA scoreboard/schedule, all-scores, or a game page")
    f = norm(fa)
    matched = []
    for away, home, asc, hsc in APR9_ESPN_GAMES:
        if (any(x in f for x in away) and any(x in f for x in home)
                and game_score_in(fa, asc, hsc)):
            matched.append((away[0], home[0], asc, hsc))
    j.check("answer_april9_espn_game", len(matched) >= 1,
            f"matched={matched}")
    j.check("answer_match_date",
            ("april 9" in f) or ("apr 9" in f) or ("4/9" in f) or ("2024-04-09" in f),
            "the match date is April 9, 2024")
    j.emit()

if __name__ == "__main__":
    main()
