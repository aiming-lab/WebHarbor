#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--6.

Task: Simplify x^5-20x^4+163x^3-676x^2+1424x-1209 so that it has fewer items.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=Simplify x^5-20x^4+163x^3-676x^2+1424x-1209 renders the
    Results pod:  (x - 4)^5 + 3 (x - 4)^3 + 7
    (the verbatim task wording itself matches this record).
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
    j = Judge('Wolfram Alpha--6', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_simplify_input_query",
          queried_with_all(t, must_all=['1209', '1424'],
                          any_of=[['simplify', 'factor']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_depressed_quintic_form", contains_any(fa, ["(x-4)^5"]) and (contains_any(fa, ["3(x-4)^3", "3*(x-4)^3"]) or contains_any(fa, ["3(x-4)³", "3·(x-4)^3"])) and bool(re.search(r"(^|[^0-9^])7([^0-9]|$)", n)), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
