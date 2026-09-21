#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--39.

Task: Use Wolfram alpha to write the expression of the ellipse x^2 + 3 y^2 = 4 rotated 33 degrees counterclockwise.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    The verbatim wording hits the axis-aligned ellipse record; the
    rotation records need either
      rotate x^2 + 3y^2 = 4 by 33 degrees -> Transformed curve:
        x^2(sin(2pi/15) - 2) + 2 x y cos(2pi/15) + 4 = y^2(2 + sin(2pi/15))
      or the substitution form (x cos 33 + y sin 33)^2 + 3 (-x sin 33 +
      y cos 33)^2 = 4 -> Result: = 1.5888 x^2 + 1.8272 x y + 2.4112 y^2 = 4
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
    j = Judge('Wolfram Alpha--39', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_rotate_ellipse_input_query",
          queried_with_all(t, must_all=['33'],
                          any_of=[['rotate', 'rotated', 'rotation'], ['x^2+3y^2', 'x^2+3y^2']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'use wolfram alpha to write', 'the expression of the ellipse', 'rotated 33 degrees counterclockwise', 'rotated ellipse', 'apply 33', 'apply 33 deg', 'write the expression']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_rotated_ellipse_expression", contains_any(fa, ["1.5888", "1.8272", "2.4112"]) or (contains_any(fa, ["sin(2pi/15)", "sin(2π/15)"]) and contains_any(fa, ["cos(2pi/15)", "cos(2π/15)", "2xy"])), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
