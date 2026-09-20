#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--11.

Task: Show the electrical resistivity of UNS A92024 and UNS G10800 at 20 degrees Celsius.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    Two /input queries are needed (the joint query is rejected by the
    mirror's verbose-wording gate):
      electrical resistivity of UNS A92024 at 20 C  -> WA display form
        9.731 x 10^-5 cm*C*ohm (rho x T); the no-temperature record
        'electrical resistivity of UNS A92024' adds: rho = 4.9 x 10^-6 ohm cm
        (= 4.87 x 10^-8 ohm m)
      electrical resistivity of UNS G10800 at 20 C  -> 3.6 x 10^-4 cm*C*ohm;
        no-temperature record: rho = 1.8 x 10^-5 ohm cm (= 1.80 x 10^-7 ohm m)
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
    j = Judge('Wolfram Alpha--11', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_resistivity_a92024_input_query",
          queried_with_all(t, must_all=['a92024', 'resistivity'],
                          any_of=[],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', '1080 steel', 'aisi 1080']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("nav_resistivity_g10800_input_query",
          queried_with_all(t, must_all=['g10800', 'resistivity'],
                          any_of=[],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'alloy 2024', 'aluminum 2024']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_resistivity_a92024", bound(fa, ["a92024", "alloy 2024", "aluminum 2024", "aluminium 2024"], ["4.87", "9.731", "4.9"]) and contains_any(fa, ["10^-8", "10^-5", "10^-6"]), f"final={fa[:200]!r}")
    j.check("answer_resistivity_g10800", bound(fa, ["g10800", "1080 steel", "aisi 1080"], ["1.80", "3.6", "1.8"]) and contains_any(fa, ["10^-7", "10^-4", "10^-5"]), f"final={fa[:200]!r}")
    j.check("answer_names_both_alloys", contains_any(fa, ["a92024", "aluminum 2024", "aluminium 2024", "alloy 2024"]) and contains_any(fa, ["g10800", "1080 steel", "aisi 1080", "1080"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
