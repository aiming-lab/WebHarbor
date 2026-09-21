#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--41.

Task: What is the approximate Heart Rate Reserve of a 50 year old man who has a heart rate of 60bpm at rest.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=heart rate reserve 50 year old man 60 bpm (parsed 'Karvonen
    heart rate reserve | gender male | age 50 yr | resting HR 60 bpm')
    renders the Result pod: heart rate reserve = 110 bpm  (= 1.833 bps)
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
    j = Judge('Wolfram Alpha--41', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_hrr_input_query",
          queried_with_all(t, must_all=['50', '60'],
                          any_of=[['heartratereserve', 'hrr', 'karvonen']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'what is the approximate', 'has a heart rate of', 'who has a heart rate', 'at rest']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_hrr_value", decimal_in(fa, "110") and contains_any(fa, ["bpm", "beats per minute", "beat/min", "bps"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
