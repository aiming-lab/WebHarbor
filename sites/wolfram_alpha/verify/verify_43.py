#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--43.

Task: A polyominoes of order 6 means you have 6 identical squares to combine different shapes (2-sided). How many combinations are there? Looking at all the shapes in the result, how many of them have only 2 rows in total?

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=polyominoes order 6 2-sided combinations 2 rows (parsed
    'Polyominoes[order=6, sides=2]') renders:
      Counts: 1-sided (free) 60; 2-sided (with chirality) 35
      Bounding-box dimensions of all 35: 1x6:1, 2x5:6, 2x4:3, 3x4:13,
        3x3:9, 2x3:3
      Hexominoes that fit in 2 rows total: 1 + 6 + 3 + 3 = 13 shapes
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
    j = Judge('Wolfram Alpha--43', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_polyomino_input_query",
          queried_with_all(t, must_all=['6'],
                          any_of=[['polyomino', 'hexomino'], ['2-sided', '2sided', 'twosided', 'two-sided', 'withchirality', 'with chirality', 'including orientation', 'with reflection', 'includingorientation', 'withreflection']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'means you have 6 identical squares', 'how many combinations are there', 'how many of them have only 2 rows', 'looking at all the shapes', 'order 6 count', 'count 2-sided']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_hexomino_counts", contains_any(fa, ["hexomino", "polyomino"]) and decimal_in(fa, "35") and decimal_in(fa, "13"), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
