#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--4.

Check ESPN for the final scores of NBA games that were played yesterday.

Ground truth (hardcoded; frozen from the served mirror pages — mirror "today"
is April 10, 2024, so yesterday = April 9, 2024, when the NBA played EIGHT
finalized games):
    Pacers 114 @ Bucks 119 (ESPN), Warriors 109 @ Nuggets 121 (TNT),
    Knicks 102 @ Heat 108 (ESPN), Mavericks 110 @ Suns 128 (ESPN),
    76ers 110 @ Celtics 118 (ESPN), Timberwolves 115 @ Thunder 121 (ESPN),
    Hawks 118 @ Cavaliers 125 (ESPN), Kings 108 @ Pelicans 116 (ESPN).

Checks: run-package gate + answer + navigation (scoreboard / schedule /
all-scores / game pages) + >=5 of the 8 games with teams and correct scores +
read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, norm, game_score_in,
                        Judge, parse_args)

APR9_GAMES = [
    (["pacer", "indiana"], ["buck", "milwaukee"], 114, 119),
    (["warrior", "golden state"], ["nugget", "denver"], 109, 121),
    (["knick", "new york"], ["heat", "miami"], 102, 108),
    (["maverick", "dallas"], ["sun", "phoenix"], 110, 128),
    (["76er", "philadelphia", "sixers"], ["celtic", "boston"], 110, 118),
    (["timberwolve", "wolves", "minnesota"], ["thunder", "okc", "oklahoma city"], 115, 121),
    (["hawk", "atlanta"], ["cavalier", "cleveland"], 118, 125),
    (["king", "sacramento"], ["pelican", "new orleans"], 108, 116),
]

def main():
    a = parse_args()
    j = Judge('ESPN--4', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_scores_pages",
            navigated_any(t, ["/nba/scoreboard", "/nba/schedule", "/scores", "/game/"]),
            "must open the NBA scoreboard/schedule, all-scores, or a game page")
    f = norm(fa)
    matched = []
    for away, home, asc, hsc in APR9_GAMES:
        if (any(x in f for x in away) and any(x in f for x in home)
                and game_score_in(fa, asc, hsc)):
            matched.append((away[0], home[0], asc, hsc))
    j.check("answer_five_yesterday_games", len(matched) >= 5,
            f"matched={len(matched)}/8: {matched}")
    j.emit()

if __name__ == "__main__":
    main()
