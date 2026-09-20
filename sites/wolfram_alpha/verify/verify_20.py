#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--20.

Task: Compute the integral of 3e^(2x) from x=0 to x=5.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=3e^(2x) integral from 0 to 5 (parsed 'integrate 3 e^(2 x)
    dx from 0 to 5') renders the Definite-integral pod:
      integral_0^5 3 e^(2 x) dx = (3/2) (e^10 - 1)  =  33038.47
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
    j = Judge('Wolfram Alpha--20', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_definite_integral_input_query",
          queried_with_all(t, must_all=['e^(2x)', '0', '5'],
                          any_of=[['3e', '3*e']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'compute the integral of 3', 'definite integral of 3', 'compute ∫', 'compute integral of 3']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_definite_integral_value", decimal_in(fa, "33038.47", tol=5) or contains_any(fa, ["(3/2)(e^10-1)", "3/2(e^10-1)", "1.5(e^10-1)", "(3/2)*(e^10-1)", "3/2*e^10", "(3/2)(e10-1)"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
