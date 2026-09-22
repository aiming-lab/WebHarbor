#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--21.

Task: Calculate (1+0.1*i)^8 + (1−0.2*i)^8  where i is a complex number.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    The verbatim wording hits the mirror's 'solve for i' quirk record
    (5 complex roots); the computation record needs
    /input?i=(1+0.1i)^8 + (1-0.2i)^8 (parsed '(1 + 0.1 i)^8 + (1 - 0.2 i)^8
    (i = imaginary unit)') which renders:
      Result: 0.717183 - 0.425258 i
      Polar form: 0.833784 e^(-0.535225 i)
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
    j = Judge('Wolfram Alpha--21', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_complex_power_input_query",
          queried_with_all(t, must_all=['0.1', '0.2', '8'],
                          any_of=[],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'where i is a complex number', 'where i is complex', 'where i is the imaginary unit', 'imaginary unit', 'i is imaginary', 'solve', 'for i']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_complex_power_result", contains_any(fa, ["0.717183-0.425258i"]) or (contains_any(fa, ["0.833784"]) and contains_any(fa, ["0.535225"])), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
