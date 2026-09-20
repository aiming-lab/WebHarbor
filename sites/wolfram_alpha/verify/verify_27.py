#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--27.

Task: Display the thermal conductivity of Copper (Cu) and Aluminum (Al) at 25 degrees Celsius.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    The joint verbatim query is rejected by the mirror's gate; two
    queries are needed:
      thermal conductivity copper at 25 c    -> Result: 401.2 W/(m K)
      thermal conductivity aluminum at 25 c  -> Result: 236.9 W/(m K)
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
    j = Judge('Wolfram Alpha--27', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_thermal_copper_input_query",
          queried_with_all(t, must_all=['copper', 'thermalconductivity'],
                          any_of=[],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'aluminum', 'aluminium']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("nav_thermal_aluminum_input_query",
          queried_with_all(t, must_all=['thermalconductivity'],
                          any_of=[['aluminum', 'aluminium']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'copper']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_both_conductivities", bound(fa, ["copper", "cu"], ["401.2"]) and bound(fa, ["aluminum", "aluminium", "al"], ["236.9"]), f"final={fa[:200]!r}")
    j.check("answer_names_both_metals", contains_any(fa, ["copper"]) and contains_any(fa, ["aluminum", "aluminium"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
