#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--24.

Task: Solve the differential equation y''(t) - 2y'(t) + 10y(t) = 0 and display its general solution.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    The verbatim wording hits the mirror's 'differential equation (general
    topic)' doesn't-understand record; the computation record needs the
    bare equation, e.g. /input?i=y''(t) - 2y'(t) + 10y(t) = 0, which
    renders the Differential-equation-solution pod:
      y(t) = c_1 e^t sin(3 t) + c_2 e^t cos(3 t)
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
    j = Judge('Wolfram Alpha--24', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_ode_input_query",
          queried_with_all(t, must_all=['10'],
                          any_of=[["y''", 'y\\"']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'find general solution', 'general solution', 'solve y double', 'y double-prime', 'solve the differential equation', 'display its general solution']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_general_solution_form", contains_any(fa, ["sin(3t)", "sin(3*t)", "sin3t", "sin3"]) and contains_any(fa, ["cos(3t)", "cos(3*t)", "cos3t", "cos3"]) and contains_any(fa, ["e^t", "exp(t)", "e^(t)", "e t"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
