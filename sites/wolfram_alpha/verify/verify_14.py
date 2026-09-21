#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--14.

Task: Compare the total Calories: whopper vs baconator vs big mac. Assume that each serving of food is 300g.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=300g whopper vs baconator vs big mac (parsed 'Burger King
    Whopper / Wendy\'s Old-Fashioned Baconator / McDonald\'s Big Mac
    (300 g each)') renders the 300 g nutrition pods:
      Whopper @ 300 g: total calories 657 Cal
      Baconator @ 300 g: total calories 902 Cal
      Big Mac @ 300 g: total calories 729 Cal
    (the per-burger-serving record shows 640/830/520 Cal -- those are
    NOT the 300 g values the task asks for; the three separate queries
    '300g whopper' / '300g baconator' / '300g big mac' render the same
    300 g values).
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
    j = Judge('Wolfram Alpha--14', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    # every burger must appear in some 300 g query (a single comparison
    # query covering all three satisfies this too)
    qs = input_queries(t)
    cov = {b: any((math_norm(b) in math_norm(q)) and ('300' in math_norm(q)) for q in qs)
           for b in ('whopper', 'baconator', 'big mac')}
    j.check('nav_300g_burger_queries', all(cov.values()), f'coverage={cov}')
    j.check("answer_300g_calorie_values", decimal_in(fa, "657") and decimal_in(fa, "902") and decimal_in(fa, "729"), f"final={fa[:200]!r}")
    j.check("answer_names_three_burgers", contains_any(fa, ["whopper"]) and contains_any(fa, ["baconator"]) and contains_any(fa, ["big mac", "bigmac", "big-mac"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
