#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--18.

Task: Plot Albert Einstein curve with Parametric equations.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=Albert Einstein curve (parsed 'first Albert Einstein curve
    (popular curve)') renders:
      Plot: hand-drawn Einstein silhouette; t from 0 to 92 pi
      Parametric equations: x(t), y(t) Fourier series (~30+ sin terms)
      Associated person: Albert Einstein
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
    j = Judge('Wolfram Alpha--18', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_einstein_curve_input_query",
          queried_with_all(t, must_all=['einstein'],
                          any_of=[['albert', 'curve']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'plot albert einstein curve with', 'curve with parametric equations']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_einstein_curve_description", contains_any(fa, ["einstein"]) and contains_any(fa, ["fourier", "parametric", "x(t)", "silhouette", "silhouette", "sin terms", "92pi", "92 pi"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
