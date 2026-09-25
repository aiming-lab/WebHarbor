#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--23.

Task: Calculate the population growth rate of Canada from 2020 to 2023 using Wolfram Alpha.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=population growth rate Canada (parsed 'Canada | population
    growth | 2020 to 2023') renders the Result pod:
      mean:    0.9886 %/yr
      lowest:  0.7392 %/yr  (2021)
      highest: 1.231  %/yr  (2023)
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
    j = Judge('Wolfram Alpha--23', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_canada_growth_input_query",
          queried_with_all(t, must_all=['canada'],
                          any_of=[['population growth', 'populationgrowth', 'growth rate']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_growth_rate_mean", decimal_in(fa, "0.9886") and (decimal_in(fa, "0.7392") or decimal_in(fa, "1.231")), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
