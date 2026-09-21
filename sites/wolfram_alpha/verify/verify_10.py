#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--10.

Task: Give the geomagnetic field on June 20, 2023 in Oslo.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=geomagnetic field on June 20 2023 in Oslo (parsed
    'GeomagneticField["Oslo", DateObject[{2023,6,20}]]') renders:
      Total field F: 51.5 uT
      Declination D: +4.51 E
      Inclination I (dip): +72.888 deg
      Components: +15.1 uT north, +1.19 uT east, +49.2 uT down
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
    j = Judge('Wolfram Alpha--10', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_geomagnetic_oslo_input_query",
          queried_with_all(t, must_all=['oslo'],
                          any_of=[['geomagnetic', 'magnetic field']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'give the geomagnetic', 'magnetic field at oslo', 'on 20 june', 'earth magnetism']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_geomagnetic_field_values", decimal_in(fa, "51.5") and contains_any(fa, ["μt", "microtesla", "micro tesla"]) and (decimal_in(fa, "4.51") or decimal_in(fa, "72.888")), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
