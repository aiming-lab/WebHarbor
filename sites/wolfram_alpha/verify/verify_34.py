#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--34.

Task: Calculate the mass of Jupiter compared to Earth using Wolfram Alpha. Also, find the length of one day on Jupiter.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    Two /input queries are needed:
      mass of Jupiter compared to Earth -> Jupiter mass 1.898 x 10^27 kg,
        Earth mass 5.972 x 10^24 kg, Jupiter/Earth = 317.8
      Jupiter rotation period (or 'Jupiter') -> rotation period
        9.925 hours (sidereal) = 9 h 55 min 30 s = 0.41354 Earth days
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
    j = Judge('Wolfram Alpha--34', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_jupiter_mass_input_query", queried_with_all(t, must_all=['jupiter', 'earth', 'mass'], any_of=[], forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'length of day', 'length of one day', 'day on jupiter', 'find the length', 'also find', 'compared to earth?', 'mass ratio jupiter', 'jupiter to earth', 'mass ratio', 'ratio jupiter']) or queried_with_all(t, must_all=['jupiter', 'mass'], any_of=[['earth']], forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'compared to earth', 'length of one day', 'also find', 'find the length']), f"input_queries={input_queries(t)[:6]}")
    j.check("nav_jupiter_day_input_query",
          queried_with_all(t, must_all=['jupiter'],
                          any_of=[],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'compared to earth', 'length of one day', 'also find', 'find the length', 'day length', 'jupiter day length', 'mass of jupiter compared', 'mass of jupiter / mass of earth', 'mass ratio', 'ratio jupiter', 'jupiter to earth']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_jupiter_mass_ratio", decimal_in(fa, "317.8") or (decimal_in(fa, "1.898") and decimal_in(fa, "5.972")), f"final={fa[:200]!r}")
    j.check("answer_jupiter_day_length", decimal_in(fa, "9.925") or contains_any(fa, ["9h55", "9 h 55", "0.413"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
