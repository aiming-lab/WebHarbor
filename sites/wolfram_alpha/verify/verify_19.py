#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--19.

Task: Standing in the sun from 11:00 am with SPF 5 in Australia. Approximate time to sunburn for each skin type.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=time to sunburn SPF 5 Australia 11 am (parsed 'time to
    sunburn (skin type=all, location=Australia, start time=11:00 am,
    SPF=5)') renders the Typical-time-to-sunburn pod:
      skin type I:   1 h 37 min
      skin type II:  2 h
      skin type III: 3 h
      skin type IV:  5 h
      skin type V:   sunburn unlikely
      skin type VI:  sunburn unlikely
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
    j = Judge('Wolfram Alpha--19', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_sunburn_australia_input_query",
          queried_with_all(t, must_all=['spf', 'australia'],
                          any_of=[['5'], ['11']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'standing in the sun', 'approximate time to sunburn for each', 'per skin type. 11']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_skin_type_i_time", contains_any(fa, ["1h37", "37min", "1 h 37", "1 hour 37", "97 min", "97min"]), f"final={fa[:200]!r}")
    j.check("answer_more_skin_types", count_named(fa, ["skintype", "skin type", "fitzpatrick"]) >= 1 and count_named(fa, ["2h", "3h", "5h", "sunburnunlikely", "unlikely", "2 h", "3 h", "5 h"]) >= 2, f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
