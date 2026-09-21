#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--15.

Task: Show the blood relationship fraction between you and your father's mother's sister's son.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=blood relationship fraction father's mother's sister's son
    (parsed 'BloodRelationship[father\'s mother\'s sister\'s son]') renders:
      Relation: your first cousin once removed
      Coefficient: 1/32 = 3.125 %
      Common ancestor: paternal great-grandparents (3 generations)
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
    j = Judge('Wolfram Alpha--15', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_blood_relationship_input_query",
          queried_with_all(t, must_all=['father', 'mother', 'sister', 'son'],
                          any_of=[['blood relationship', 'bloodrelationship', 'relationship fraction', 'blood relation']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'show the blood relationship', 'between you and your', 'blood relationship fraction between']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_relationship_fraction", contains_any(fa, ["1/32", "3.125"]) and contains_any(fa, ["first cousin once removed", "first cousin"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
