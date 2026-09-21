#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--12.

Task: Which character in unicode 8900 to 8920 looks like a snowflake

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=unicode 8900 to 8920 renders the 21-character list including
      U+22C6 (8902)  STAR OPERATOR (glyph a four-pointed star)
    and /input?i=unicode 8902 renders the single-character record:
      Glyph, Name STAR OPERATOR, Code U+22C6 (decimal 8902)
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
    j = Judge('Wolfram Alpha--12', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_unicode_snowflake_input_query", queried_with_all(t, must_all=['unicode', '8900', '8920'], any_of=[], forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'which character', 'looks like a snowflake', 'looks like snowflake']) or queried_with_all(t, must_all=['unicode', '8902'], any_of=[], forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to']), f"input_queries={input_queries(t)[:6]}")
    j.check("answer_star_operator_character", contains_any(fa, ["8902", "22c6"]) and contains_any(fa, ["star operator", "⋆", "snowflake"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
