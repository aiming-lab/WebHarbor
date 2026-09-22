#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--3.

Task: Let g(x) be the integral of x^2 cos(2x). Write the expression of g(x).

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=integral of x^2 cos(2x) (parsed 'integrate x^2 cos(2 x) dx')
    renders the Indefinite-integral pod:
      (1/4) ((2 x^2 - 1) sin(2x) + 2 x cos(2x)) + C
    and the Expanded pod:
      (1/2) x^2 sin(2x) + (1/2) x cos(2x) - (1/4) sin(2x) + C
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
    j = Judge('Wolfram Alpha--3', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_integral_input_query",
          queried_with_all(t, must_all=['x^2'],
                          any_of=[['cos(2x)', 'cos(2*x)', 'cos2x']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'let g(x) be', 'write the expression', 'write the expression of']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_antiderivative_expression", contains_all(fa, ["sin(2x)", "cos(2x)"]) and contains_any(fa, ["1/4", "0.25", "1/2", "0.5", "(2x^2-1)", "2x^2-1"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
