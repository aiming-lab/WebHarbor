#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--25.

Identify the player with the most assists in the latest NBA game and show me
the assists, the team they play for, and their position.

Ground truth (hardcoded; frozen from the served pages — the latest completed
NBA games are the eight April 9, 2024 games; each accepted answer is the
game-high assist man of one of those games, with assists, team, and the
position shown on the player's ESPN profile):
    Tyrese Haliburton 11 (Pacers, PG), Nikola Jokic 12 (Nuggets, C),
    Tyler Herro 8 (Heat, SG), Devin Booker 8 (Suns, SG), Jrue Holiday 8
    (Celtics, PG), Jalen Williams 8 (Thunder, SF), Darius Garland 8
    (Cavaliers, PG), CJ McCollum 8 (Pelicans, SG).

Checks: run-package gate + answer + navigation (game page / scoreboard /
player profile) + one accepted game-high assists leader with assists, team,
and position + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_any, num_in,
                        pos_in, Judge, parse_args)

AST_LEADERS = [
    (["haliburton"], 11, ["pacer", "indiana"], ["pg"]),
    (["jokic"], 12, ["nugget", "denver"], ["c"]),
    (["herro"], 8, ["heat", "miami"], ["sg"]),
    (["booker"], 8, ["sun", "phoenix"], ["sg"]),
    (["holiday"], 8, ["celtic", "boston"], ["pg"]),
    (["jalen williams"], 8, ["thunder", "okc", "oklahoma city"], ["sf"]),
    (["garland"], 8, ["cavalier", "cleveland"], ["pg"]),
    (["mccollum"], 8, ["pelican", "new orleans"], ["sg"]),
]

def main():
    a = parse_args()
    j = Judge('ESPN--25', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_game_or_player",
            navigated_any(t, ["/game/", "/nba/scoreboard", "/nba/schedule",
                              "/scores", "/player/nba/"]),
            "must open a game page, the scoreboard/schedule, or a player profile")
    matched = []
    for names, ast, team_toks, positions in AST_LEADERS:
        if (any(n in fa.lower() for n in names) and num_in(fa, ast)
                and any(x in fa.lower() for x in team_toks) and pos_in(fa, positions)):
            matched.append(names[0])
    j.check("answer_gamehigh_assists", len(matched) >= 1,
            f"accepted game-high assist men matched={matched}")
    j.emit()

if __name__ == "__main__":
    main()
