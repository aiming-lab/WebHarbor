#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--38.

Task: Compute the length of a curve defined by y = 2x^3 - 3x^2 + 4x - 5 from x = 0 to x = 3.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=arc length of 2x^3 - 3x^2 + 4x - 5 from 0 to 3 (parsed
    'ArcLength[{x, 2 x^3 - 3 x^2 + 4 x - 5}, {x, 0, 3}]') renders the
    Result pod: L = 39.249927
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
    j = Judge('Wolfram Alpha--38', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_arc_length_input_query",
          queried_with_all(t, must_all=['2x^3'],
                          any_of=[['arclength', 'lengthofcurve', 'lengthofacurve', 'lengthofthecurve', 'curvelength']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'compute the length of a curve', 'length of a curve defined by', 'curve defined by y =']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_arc_length_value", decimal_in(fa, "39.249927", tol=0.0005) or decimal_in(fa, "39.25", tol=0.005), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
