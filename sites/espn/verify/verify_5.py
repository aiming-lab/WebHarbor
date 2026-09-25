#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--5.

Identify the top scorer in the NBA from the latest completed game and note
down the points scored, the team they play for, and their position on the team.

Ground truth (hardcoded; frozen from the served mirror pages — the latest
completed NBA games are the eight April 9, 2024 games; each accepted answer is
the GAME-HIGH scorer of one of those games, with points, team, and the
position shown on the player's ESPN profile):
    Giannis Antetokounmpo 35 (Bucks, PF), Nikola Jokic 29 (Nuggets, C),
    Jalen Brunson 36 (Knicks, PG), Kevin Durant 33 (Suns, PF),
    Jayson Tatum 31 (Celtics, SF), Shai Gilgeous-Alexander 34 (Thunder, PG),
    Donovan Mitchell 35 (Cavaliers, SG), Zion Williamson 28 (Pelicans, PF).

Checks: run-package gate + answer + navigation (scoreboard / game detail /
player profile) + one accepted game-high scorer with points, team, position +
read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_any, num_in,
                        pos_in, Judge, parse_args)

TOP_SCORERS = [
    (["giannis", "antetokounmpo"], 35, ["buck", "milwaukee"], ["pf"]),
    (["jokic"], 29, ["nugget", "denver"], ["c"]),
    (["brunson"], 36, ["knick", "new york"], ["pg"]),
    (["durant"], 33, ["sun", "phoenix"], ["pf"]),
    (["tatum"], 31, ["celtic", "boston"], ["sf"]),
    (["gilgeous-alexander", "shai", "sga"], 34, ["thunder", "okc", "oklahoma city"], ["pg"]),
    (["mitchell"], 35, ["cavalier", "cleveland"], ["sg"]),
    (["zion", "williamson"], 28, ["pelican", "new orleans"], ["pf"]),
]

def main():
    a = parse_args()
    j = Judge('ESPN--5', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_game_or_player",
            navigated_any(t, ["/game/", "/nba/scoreboard", "/nba/schedule",
                              "/scores", "/player/nba/"]),
            "must open a game page, the scoreboard/schedule, or a player profile")
    matched = []
    for names, pts, team_toks, positions in TOP_SCORERS:
        if (any(n in fa.lower() for n in names) and num_in(fa, pts)
                and any(x in fa.lower() for x in team_toks) and pos_in(fa, positions)):
            matched.append(names[0])
    j.check("answer_gamehigh_scorer", len(matched) >= 1,
            f"accepted game-high scorers matched={matched}")
    j.emit()

if __name__ == "__main__":
    main()
