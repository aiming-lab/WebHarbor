#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--5.

Task: Show the solution of y"(z) + sin(y(z)) = 0 from wolframalpha.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=solution of y''(z) + sin(y(z)) = 0 renders the
    Differential-equation-solution pod:
      y(z) = -2 am((1/2) sqrt((c1+2) (z+c2)^2) | 4/(c1+2))
      y(z) = +2 am((1/2) sqrt((c1+2) (z+c2)^2) | 4/(c1+2))
    where am(z|m) is the Jacobi amplitude function (pendulum equation).
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
    j = Judge('Wolfram Alpha--5', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_pendulum_ode_input_query",
          queried_with_all(t, must_all=['sin(y(z))', '0'],
                          any_of=[["y''", 'y\\"']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'from wolframalpha', 'pendulum equation', 'find solution', 'y double-prime']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_jacobi_amplitude_solution", contains_any(fa, ["am(", "jacobi"]) and contains_any(fa, ["c1", "c_1", "c2", "c_2"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
