#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--33.

Task: Identify the electrical energy output of a hydroelectric power plant named Itaipu Dam in 2023 using Wolfram Alpha.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    The verbatim wording is rejected; /input?i=Itaipu Dam (parsed 'Itaipu
    Dam (hydroelectric power plant)') renders the Generation pod:
      annual power generation: 89.5 TWh  (= 3.222 x 10^17 J/yr)
    The mirror has no 2023-specific Itaipu record (the bare 'Itaipu 2023'
    query hits a calendar-year quirk record).
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
    j = Judge('Wolfram Alpha--33', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_itaipu_input_query",
          queried_with_all(t, must_all=['itaipu'],
                          any_of=[['dam']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'identify the electrical energy output', 'hydroelectric power plant named', 'itaipu dam in 2023 using', 'in 2023', 'electricity output', 'annual generation in', 'identify the']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_annual_generation", decimal_in(fa, "89.5") and contains_any(fa, ["twh", "terawatt", "3.222"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
