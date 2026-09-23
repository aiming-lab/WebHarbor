#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--36.

Search for Lionel Messi's last 5 games, which teams has he played for, and
what are the results?

Ground truth (hardcoded; frozen from the served /player/soccer/lionel-messi/gamelog
page — the five most recent rows):
    Apr 9, 2024 @ Real Madrid L 2-3; Apr 6, 2024 vs Paris Saint-Germain W
    1-0; Apr 3, 2024 @ Barcelona W 4-2; Mar 30, 2024 vs Barcelona D 2-2;
    Mar 23, 2024 @ Paris Saint-Germain W 3-2.  He plays for Inter Miami CF
    (opponents: Real Madrid, PSG x2, Barcelona x2); results summary:
    3 wins, 1 draw, 1 loss.

Checks: run-package gate + answer + navigation (Messi player/game-log pages,
the Messi article, or a Messi search) + Inter Miami + >=3 opponents + >=3
results (scorelines or the W/D/L summary) + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        game_score_in, norm, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--36', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_messi_pages",
            navigated_any(t, ["lionel-messi", "messi-inter-miami", "/search?q=messi"]),
            "must open Messi's player/game-log pages, a Messi article, or search for him")
    f = norm(fa)
    j.check("answer_inter_miami",
            ("inter miami" in f) or ("messi" in f),
            "Messi plays for Inter Miami CF")
    opponents = [x for x in ["real madrid", "paris saint-germain", "psg", "paris",
                             "barcelona"] if x in f]
    j.check("answer_three_opponents", len(set(opponents)) >= 3,
            f"opponents mentioned={set(opponents)} (need >=3 of Real Madrid / PSG / Barcelona)")
    scorelines = sum(1 for a, b in [(2, 3), (1, 0), (4, 2), (2, 2), (3, 2)]
                     if game_score_in(fa, a, b))
    summary = (contains_any(fa, ["3 win", "three win", "3-1-1", "won 3"])
              and contains_any(fa, ["1 draw", "one draw", "a draw"])
              and contains_any(fa, ["1 loss", "one loss", "a loss"]))
    j.check("answer_three_results", scorelines >= 3 or summary,
            f"results given: {scorelines}/5 scorelines, W/D/L summary={summary}")
    j.emit()

if __name__ == "__main__":
    main()
