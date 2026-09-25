#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--40.

Browse the ESPN+ page from ESPN for a brief summary of what ESPN+ Tools is
used for.

Ground truth (hardcoded; frozen from the served /espnplus page's Tools
section):
    'ESPN+ Tools is a suite of analytics, projections, and trade calculators
    that help fans research matchups, build fantasy lineups, and dig into
    advanced stats. It bundles the Trade Machine, Player Rater, Mock Draft,
    Bracket Predictor, and FPI / BPI projection dashboards in one
    subscriber-only workspace.'

Checks: run-package gate + answer + navigation to the ESPN+ page + >=3
distinctive facts from the Tools description + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--40', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_espnplus", navigated_any(t, ["/espnplus", "/espn-plus"]),
            "must open the ESPN+ page")
    facts = [
        contains_any(fa, ["analytics"]),
        contains_any(fa, ["projection"]),
        contains_any(fa, ["trade calculator"]),
        contains_any(fa, ["fantasy lineup"]),
        contains_any(fa, ["trade machine"]),
        contains_any(fa, ["player rater"]),
        contains_any(fa, ["mock draft"]),
        contains_any(fa, ["bracket predictor"]),
        contains_any(fa, ["advanced stat"]),
        contains_any(fa, ["subscriber"]),
        contains_any(fa, ["research matchup", "matchups"]),
    ]
    j.check("answer_three_tool_facts", sum(1 for x in facts if x) >= 3,
            f"ESPN+ Tools facts matched={sum(1 for x in facts if x)}/11")
    j.emit()

if __name__ == "__main__":
    main()
