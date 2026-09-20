#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--45.

Task: A 175cm tall, 85kg, 40yo man climbs 2500 steps at about 18cm per step and 40 steps per minute. summarise the Metabolic properties.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=climbing stairs 175cm 85kg 40 year old 2500 steps 40
    steps/min (parsed 'stair climbing | male | 175 cm | 85 kg | 40 yr |
    2500 steps | step rate 40 /min | step height 6 in (default)') renders
    the Metabolic-properties pod:
      energy expenditure: = 597 Cal
      fat burned: = 0.1706 lb
      oxygen consumption: = 31.54 gal
      metabolic equivalents: 6.4 MET
      per-step energy: = 0.24 Cal/step
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
    j = Judge('Wolfram Alpha--45', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_stair_climbing_input_query",
          queried_with_all(t, must_all=['175', '85', '2500'],
                          any_of=[['stairclimbing', 'climbingstairs', 'stair-climbing', 'climbstair', 'climbs']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'summarise the metabolic properties', 'summarize the metabolic properties', '40yo man climbs', 'at about 18cm per step']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_metabolic_properties", decimal_in(fa, "597") and (decimal_in(fa, "6.4") or decimal_in(fa, "0.1706") or decimal_in(fa, "31.54") or decimal_in(fa, "0.24")), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
