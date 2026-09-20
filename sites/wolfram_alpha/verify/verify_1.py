#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--1.

Task: Give a constraint on the set of inequalities for the inner region of the pentagram.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    The task's verbatim wording returns the mirror's 'doesn't understand'
    record; /input?i=pentagram (parsed 'Pentagram (regular star polygon,
    lamina)') renders the 'Defining inequalities' pod:
      2 a + 3 sqrt(5) x + 5 x >= sqrt(2 (5 + sqrt(5))) y
      sqrt(5) a + 2 sqrt(5) x + 2 sqrt(5 + 2 sqrt(5)) y <= a  (and more clauses)
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
    j = Judge('Wolfram Alpha--1', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_pentagram_input_query",
          queried_with_all(t, must_all=['pentagram'],
                          any_of=[],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'inequalit', 'constraint on', 'inner region', 'central pentagon']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_inequality_constraint", contains_any(fa, ["3sqrt(5)x+5x", "sqrt(2(5+sqrt(5)))y", "sqrt(5+2sqrt(5))", "2sqrt(5+2sqrt(5))y", "2a+3sqrt(5)x"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
