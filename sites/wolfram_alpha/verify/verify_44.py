#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--44.

Task: Solve the ODE, g' + cos(g) = 0, if there is a constant in the result, determine the value of the constant by the condition that g(0) = 1.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=g' + cos(g) = 0 with g(0) = 1 (parsed "solve, g'(x) +
    cos(g(x)) = 0, g(0) = 1") renders:
      Implicit closed form: log|sec g + tan g| = -t + 1.22617
      Differential equation solution:
        g(t) = -arcsin( coth( t - arccoth( sin(1) ) ) )
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
    j = Judge('Wolfram Alpha--44', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_ode_constant_input_query",
          queried_with_all(t, must_all=['cos(g', 'g(0)=1'],
                          any_of=[],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'solve the ode', 'if there is a constant in the result', 'determine the value of the constant by the condition', 'pin the constant']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_pinned_constant_solution", decimal_in(fa, "1.22617", tol=0.00001) or (contains_any(fa, ["arccoth"]) and contains_any(fa, ["sin(1)", "sin1"])), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
