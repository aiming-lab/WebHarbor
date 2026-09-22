#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--22.

Task: Determine the area of a regular hexagon with a side length of 7 cm.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=area of regular hexagon side 7 cm (parsed 'regular hexagon
    | edge length 7 cm | area') renders the Result pod:
      (147 sqrt(3))/2 cm^2 = 127.306 cm^2
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
    j = Judge('Wolfram Alpha--22', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_hexagon_area_input_query",
          queried_with_all(t, must_all=['hexagon'],
                          any_of=[['area'], ['7']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'determine the area of a regular hexagon', 'with a side length of 7 cm', 'side 7 centimeters', 'hexagon area at', 'compute area regular']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_hexagon_area", value_unit(fa, ["127.306", "127.31"], ["cm", "centimeter", "centimetre", "squarecentimeter", "squarecentimetre", "sqcm"]) or value_unit(fa, ["12731"], ["mm", "millimeter", "millimetre", "squaremillimeter", "squaremillimetre", "sqmm"]) or contains_any(fa, ["(147sqrt3)/2cm", "(147sqrt(3))/2cm", "73.5sqrt3cm", "73.5sqrt(3)cm", "147sqrt3)/2cm", "147sqrt(3))/2cm"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
