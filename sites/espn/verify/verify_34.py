#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--34.

Visit ESPN to view the Philadelphia 76ers' latest injuries.

Ground truth (hardcoded; frozen from the served /team/nba/philadelphia-76ers/
injuries page):
    Joel Embiid C — OUT — Knee injury - left knee; Tobias Harris PF —
    DAY-TO-DAY — Ankle - right ankle soreness; Robert Covington SF — OUT —
    Knee - left knee surgery; De'Anthony Melton SG — OUT — Back - lumbar
    strain; Mo Bamba C — DAY-TO-DAY — Knee - right knee soreness; Kelly Oubre
    Jr. SF — QUESTIONABLE — Hand - left hand contusion; Nico Batum PF —
    PROBABLE — Hamstring - left hamstring tightness; Cam Payne PG —
    DAY-TO-DAY — Foot - right foot soreness; Paul Reed PF — QUESTIONABLE —
    Knee - right knee soreness; KJ Martin PF — PROBABLE — Ankle - left ankle
    sprain.

Checks: run-package gate + answer + navigation to a 76ers page + Embiid
(OUT, knee) + Harris (ankle / day-to-day) + at least one more injured player
+ read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, contains_all, contains_any,
                        word_in, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--34', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_sixers_page", navigated_to(t, "philadelphia-76ers"),
            "must open a Philadelphia 76ers page (team / injuries)")
    j.check("answer_embiid",
            contains_any(fa, ["embiid"]) and contains_any(fa, ["knee"])
            and (word_in(fa, "out") or contains_any(fa, ["indefinitely", "ruled out"])),
            "Joel Embiid OUT — left knee")
    j.check("answer_harris",
            contains_any(fa, ["harris"]) and
            (contains_any(fa, ["ankle", "day-to-day", "day to day"])),
            "Tobias Harris DAY-TO-DAY — right ankle soreness")
    more = [x for x in ["covington", "melton", "bamba", "oubre", "batum",
                        "payne", "paul reed", "kj martin", "martin"] if x in fa.lower()]
    j.check("answer_more_injuries", len(more) >= 1,
            f"additional injured players reported={more}")
    j.emit()

if __name__ == "__main__":
    main()
