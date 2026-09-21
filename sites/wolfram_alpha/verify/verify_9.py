#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--9.

Task: Annual energy production of Diablo Canyon 2 in 2010.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=Diablo Canyon 2 annual energy production 2010 (parsed
    'Diablo Canyon-2 (nuclear reactor) | annual energy production | 2010')
    renders the Result pod: 9752 GWh/yr (gigawatt hours per year)
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
    j = Judge('Wolfram Alpha--9', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_diablo_2010_input_query",
          queried_with_all(t, must_all=['diablo', 'canyon', '2010'],
                          any_of=[['annual energy production', 'annual generation', 'energy production', 'generation']],
                          forbidden=['annual energy production of', 'energy production of diablo', 'output of diablo', 'how much energy', 'did diablo', 'production of diablo canyon 2 in 2010', 'energy production of diablo', 'find the', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a', 'what are the', 'how many', 'how much', 'tell me', 'give me', 'show me', 'display the', 'show the']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_2010_energy_production", decimal_in(fa, "9752") and contains_any(fa, ["gwh", "gigawatt"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
