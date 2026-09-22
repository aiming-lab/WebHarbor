#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--32.

Review yesterday's NHL game results on ESPN, focusing on teams' performance.

Ground truth (hardcoded; frozen from the served /nhl/scoreboard page — mirror
"today" is April 10, 2024, so yesterday = April 9, 2024 with SIX NHL games):
    Rangers 2 @ Bruins 4 (TD Garden), Oilers 2 @ Golden Knights 3 (T-Mobile
    Arena), Panthers 1 @ Maple Leafs 3 (Scotiabank Arena), Oilers 4 @
    Avalanche 5 (Ball Arena), Predators 2 @ Stars 4 (American Airlines Center),
    Devils 2 @ Hurricanes 3 (PNC Arena).  Card leaders: Pastrnak 2 PTS, Mark
    Stone 1 PTS, Auston Matthews 2 PTS, MacKinnon 2 / McDavid 2, ...

Checks: run-package gate + answer + navigation (NHL scoreboard/schedule /
all-scores / game pages) + >=4 of the 6 games with teams and correct
scorelines + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, norm, game_score_in,
                        Judge, parse_args)

APR9_NHL_GAMES = [
    (["ranger", "new york"], ["bruin", "boston"], 2, 4),
    (["oiler", "edmonton"], ["golden knights", "vegas"], 2, 3),
    (["panther", "florida"], ["maple leaf", "leafs", "toronto"], 1, 3),
    (["oiler", "edmonton"], ["avalanche", "colorado"], 4, 5),
    (["predator", "nashville"], ["stars", "dallas"], 2, 4),
    (["devil", "new jersey"], ["hurricane", "carolina"], 2, 3),
]

def main():
    a = parse_args()
    j = Judge('ESPN--32', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_nhl_scores",
            navigated_any(t, ["/nhl/scoreboard", "/nhl/schedule", "/scores", "/game/"]),
            "must open the NHL scoreboard/schedule, all-scores, or a game page")
    f = norm(fa)
    matched = []
    for away, home, asc, hsc in APR9_NHL_GAMES:
        if (any(x in f for x in away) and any(x in f for x in home)
                and game_score_in(fa, asc, hsc)):
            matched.append((away[0], home[0], asc, hsc))
    j.check("answer_four_nhl_games", len(matched) >= 4,
            f"matched={len(matched)}/6: {matched}")
    j.emit()

if __name__ == "__main__":
    main()
