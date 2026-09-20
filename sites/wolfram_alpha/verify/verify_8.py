#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--8.

Task: Give 12 lbs of 4-cyanoindole, converted to molar and indicate the percentage of C, H, N.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=12 lbs of 4-cyanoindole to moles percentage C H N renders:
      Conversion: 12 lb = 5442.8 g -> 38.29 mol
      Percent composition: C: 76.04 %  H: 4.25 %  N: 19.71 %
    (the alternative record for '12 lb 4-cyanoindole' shows the same
    percentages with molar amount 38.3 mol).
Checks (deterministic only): run-package gate + non-empty answer +
read-only user-state DB + /input navigation (anti-shortcut) + answer facts.
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, input_queries, queried_with_all,
                        math_norm, norm, contains_all, contains_any,
                        decimal_in, count_named, bound, bound_nearest,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge('Wolfram Alpha--8', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_cyanoindole_input_query",
          queried_with_all(t, must_all=['4-cyanoindole', '12'],
                          any_of=[],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'molar amount and percent', 'how many moles', 'convert 12 pounds', '12 pounds of', '12 lb of 4-cyanoindole molar']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_molar_and_percent_composition", (decimal_in(fa, "38.29") or decimal_in(fa, "38.3")) and decimal_in(fa, "76.04") and decimal_in(fa, "4.25") and decimal_in(fa, "19.71"), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
