#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--2.

Task: Calculate 3^71 and retain 5 significant figures in scientific notation.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=3^71 renders the Scientific-notation pod:
      7.509466514979724803946715958257547 x 10^33
    (plus Result 7509466514979724803946715958257547, 34 decimal digits).
    5 significant figures => 7.5095 x 10^33.
Checks (deterministic only): run-package gate + non-empty answer +
read-only user-state DB + /input navigation (anti-shortcut) + answer facts.
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, input_queries, queried_with_all,
                        math_norm, norm, contains_all, contains_any,
                        decimal_in, count_named, bound, bound_nearest,
                        bound_preceding, in_order, value_unit,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge('Wolfram Alpha--2', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_3pow71_input_query",
          queried_with_all(t, must_all=[],
                          any_of=[['3^71', '3**71']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'retain 5', 'retain  5', 'retain five', '5 significant figure', 'five significant figure', 'three to the', 'to the 71', 'what is 3^71', 'in scientific notation?']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_5_sig_fig_scientific", contains_any(fa, ["7.5095"]) and contains_any(fa, ["10^33", "e+33", "e33", "10**33"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
