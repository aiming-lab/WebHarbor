#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--4.

Task: Pack 24 circles in a circle radius r. Compare Densest known packing and Square packing. Then tell me the radius of the inner circles.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=Pack 24 circles in a circle (parsed 'CirclePacking[24, Circle]')
    renders three pods:
      Densest known:  r = 0.176939 R; 75.14% filled
      Hexagonal:     r = 0.169724 R; 69.14% filled
      Square packing: r = 0.163961 R; 64.52% filled
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
    j = Judge('Wolfram Alpha--4', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_circle_packing_input_query",
          queried_with_all(t, must_all=['24'],
                          any_of=[['pack', 'packing'], ['circles', 'circle']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'compare densest known packing and square packing', 'compare densest known', 'tell me the radius', 'square packing. then', 'square packing then', 'find the radius', 'find the inner', 'inner circles when', 'densest known radius']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_densest_and_square_radii", decimal_in(fa, "0.176939") and decimal_in(fa, "0.163961"), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
