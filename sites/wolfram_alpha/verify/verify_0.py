#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--0.

Task: derivative of x^2 when x=5.6

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=d/dx x^2 at 5.6  (parsed 'd/dx (x^2) at x = 5.6') renders:
      Result pod: 'Derivative: 2 x.  Value at x = 5.6: 11.2'
    The task's verbatim wording is rejected by the mirror's gate
    ('when x='), so the agent must submit a canonical derivative query.
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
    j = Judge('Wolfram Alpha--0', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_derivative_input_query",
          queried_with_all(t, must_all=['5.6'],
                          any_of=[['x^2', 'x**2'], ['derivative', 'd/dx', 'differentiat']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'when x=', 'when x =', 'derivative of x^2 when', 'evaluated at x', 'when x equals', 'at the point x', 'find the derivative']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_derivative_value", decimal_in(fa, "11.2"), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
