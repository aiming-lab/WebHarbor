#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--37.

Task: How many days are there between February 12, 2024 and August 9, 2050?

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=days between February 12 2024 and August 9 2050 (parsed
    'days from Monday, February 12, 2024 to Tuesday, August 9, 2050')
    renders the Result pod: 9675 days
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
    j = Judge('Wolfram Alpha--37', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_days_between_input_query",
          queried_with_all(t, must_all=['2024', '2050'],
                          any_of=[['days between', 'days from', 'how many days', 'day count', 'days']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'how many days are there between', 'how many days are there', 'days from feb 12', 'days from february 12']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_day_count", decimal_in(fa, "9675") and contains_any(fa, ["day", "days"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
