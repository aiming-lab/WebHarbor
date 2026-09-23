#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--29.

Identify today's top headline in the Soccer section of ESPN, and summarize
the main points of that article.

Ground truth (hardcoded; frozen from the served /soccer/ 'TOP STORIES'
section — the first headline is):
    'Champions League quarter-final preview: Real Madrid vs Manchester City
    headlines second leg' (April 9, 2024; subtitle: 'Two heavyweight ties
    decide the semi-final lineup as the second legs unfold this week.').
    Main points: Real Madrid host Manchester City in the second leg, level on
    aggregate at the Bernabeu; Ancelotti expected to start Vinicius Junior
    and Jude Bellingham; Guardiola hinting at a midfield reshuffle; Bayern
    Munich vs Arsenal sits at 2-2 with Harry Kane in his most prolific
    European campaign; expected-goals models slightly favor the home sides;
    half-time tactical adjustments likely decide who advances to the
    semi-finals.

Checks: run-package gate + answer + navigation (Soccer section/news or the
article) + the headline subjects + >=2 detail facts + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--29', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_soccer_section",
            navigated_any(t, ["/soccer", "/story/champions-league-quarter-final"]),
            "must open the Soccer section/news or the headline article")
    j.check("answer_headline_subjects",
            contains_any(fa, ["real madrid"]) and
            contains_any(fa, ["manchester city"]),
            "top soccer headline: Real Madrid vs Manchester City Champions League preview")
    details = [contains_any(fa, ["second leg", "2nd leg"]),
               contains_any(fa, ["bernabeu", "bernabéu"]),
               contains_any(fa, ["bellingham"]),
               contains_any(fa, ["vinicius", "vinícius"]),
               contains_any(fa, ["ancelotti"]),
               contains_any(fa, ["guardiola"]),
               contains_any(fa, ["bayern"]),
               contains_any(fa, ["arsenal"]),
               contains_any(fa, ["kane"]),
               contains_any(fa, ["aggregate"]),
               contains_any(fa, ["semi-final", "semifinal"])]
    j.check("answer_main_points", sum(1 for d in details if d) >= 2,
            f"summary details matched={sum(1 for d in details if d)}/11")
    j.emit()

if __name__ == "__main__":
    main()
