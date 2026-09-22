#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--13.

Task: What is 10,000 US dollars worth now in 1980 and in 1970?

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    Two /input queries are needed (a joint query is rejected by the
    mirror's gate):
      $10000 in 1980 -> Result: $2514.25 (1980 US dollars)
      $10000 in 1970 -> Result: $1184.54 (1970 US dollars)
        ('10000 USD in 1970' renders the sibling record: ~= $1,184.36)
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
    j = Judge('Wolfram Alpha--13', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_dollars_1980_input_query",
          queried_with_all(t, must_all=['10000', '1980'],
                          any_of=[],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', '1980 dollar', 'and in 1970', 'how much was', 'today equivalent in', 'inflation: $10000', 'worth in 1980?']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("nav_dollars_1970_input_query",
          queried_with_all(t, must_all=['10000', '1970'],
                          any_of=[],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', '1970 dollar', 'and in 1980', 'how much was', 'today equivalent in 1970', 'inflation: $10000', 'worth in 1970?', 'and 1980', 'in 1970 us']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_1980_value", bound_nearest(fa, ["1980"], ["2514.25"], other_anchors=["1970"]), f"final={fa[:200]!r}")
    j.check("answer_1970_value", bound_nearest(fa, ["1970"], ["1184.54", "1184.36"], other_anchors=["1980"]), f"final={fa[:200]!r}")
    j.check("answer_names_both_years", contains_any(fa, ["1980"]) and contains_any(fa, ["1970"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
