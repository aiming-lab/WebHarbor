#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--30.

Task: Calculate the estimated time to sunburn for different skin types when exposed to the sun at 1:00 pm with SPF 1 in Brazil.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=sunburn 1:00 pm SPF 1 Brazil hits the mirror's
    disambiguation quirk (El Brazil, Texas) whose note says to use a
    Brazilian city qualifier; the country answer is
    /input?i=sunburn 1:00 pm SPF 1 Brasilia Brazil (parsed 'time to
    sunburn (skin type=all, location=Brasilia Brazil, time=13:00 UTC-3,
    SPF 1)') which renders:
      location: Brasilia-Plano Piloto, Brazil
      skin type I: 17 min / II: 22 min / III: 32 min / IV: 43 min /
      V: 1 h 1 min / VI: 3 h
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
    j = Judge('Wolfram Alpha--30', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_sunburn_brasilia_input_query",
          queried_with_all(t, must_all=['spf', 'sunburn', 'brasilia'],
                          any_of=[],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'calculate the estimated time to sunburn', 'when exposed to the sun', 'per skin type. brazil']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_brasilia_location", contains_any(fa, ["brasilia", "brasília"]), f"final={fa[:200]!r}")
    j.check("answer_skin_type_times", decimal_in(fa, "17") and decimal_in(fa, "22") and decimal_in(fa, "32") and decimal_in(fa, "43"), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
