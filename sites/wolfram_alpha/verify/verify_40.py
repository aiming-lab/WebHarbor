#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--40.

Task: Approximate amount of fat burned by a 28yo, 172cm tall, 70kg woman running for 30min at a pace of 6min/mile.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=fat burned 28 year old woman 172 cm 70 kg running 30 min
    6 min/mile pace (parsed 'FatBurn[female, 28 yr, 172 cm, 70 kg, run
    30 min @ 6 min/mile]') renders the Metabolic-properties pod:
      energy expenditure: 600 Cal
      fat burned: 0.17 lb
      oxygen consumption: 31.7 gallons
      metabolic equivalents: 16 METs
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
    j = Judge('Wolfram Alpha--40', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_fat_burn_input_query",
          queried_with_all(t, must_all=['28', '172', '70'],
                          any_of=[['fatburned', 'fatburn', 'fat burn']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'approximate amount of fat burned', 'by a 28yo', '172cm tall', 'running for 30min at a pace']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_fat_burned", decimal_in(fa, "0.17") and contains_any(fa, ["lb", "pound", "600", "16met", "31.7"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
