#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--43.

Check out NCAAW recruiting on ESPN, what colleges are the top three players
from?

Ground truth (hardcoded; frozen from the served
/womens-college-basketball/recruiting page — top three 2024 recruits):
    1. Paige Bueckers (G) — UConn; 2. Aaliyah Edwards (F) — Stanford;
    3. Olivia Miles (G) — USC.  (The 'NCAAW Top Recruits' article claims UConn /
    South Carolina / Notre Dame, which contradicts the recruiting page; the
    recruiting page is the task's named source.)

Checks: run-package gate + answer + navigation to the NCAAW recruiting page +
the three colleges (UConn, Stanford, USC) + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, contains_all, contains_any,
                        norm, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--43', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_recruiting", navigated_to(t, "recruiting"),
            "must open the NCAAW recruiting page")
    f = norm(fa)
    j.check("answer_uconn", "uconn" in f, "No. 1 recruit committed to UConn")
    j.check("answer_stanford", "stanford" in f, "No. 2 recruit committed to Stanford")
    j.check("answer_usc", ("usc" in f.replace("usc", " usc ")) or ("southern california" in f),
            "No. 3 recruit committed to USC")
    j.emit()

if __name__ == "__main__":
    main()
