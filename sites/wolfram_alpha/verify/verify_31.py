#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--31.

Task: Using Wolfram Alpha, determine the current temperature and wind speed in Chicago, IL.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=current temperature wind speed Chicago IL (parsed
    'Chicago, Illinois | temperature, wind speed') renders the Result pod:
      temperature 54 F | wind 16 mph SSW
    and the Details pod: conditions partly cloudy, humidity 59 %.
    ('Chicago weather' renders the same frozen seed values.)
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
    j = Judge('Wolfram Alpha--31', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_chicago_weather_input_query",
          queried_with_all(t, must_all=['chicago'],
                          any_of=[['temperature', 'weather'], ['wind']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'using wolfram alpha and determine', 'determine the current temperature', 'wind speed in chicago il', 'chicago il current temperature wind speed', 'using wolfram alpha', 'current temperature and wind', 'chicago il.']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_temperature_and_wind", decimal_in(fa, "54") and decimal_in(fa, "16") and contains_any(fa, ["ssw", "south-southwest", "south by south", "south"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
