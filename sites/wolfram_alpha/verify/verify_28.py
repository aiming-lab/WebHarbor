#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--28.

Task: Identify the character in Unicode range 9632 to 9650 that represents a hollow parallelogram.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=unicode 9632 to 9650 renders the character grid ending at
      9649  U+25B1  (white parallelogram glyph)
    and /input?i=unicode 9649 renders the single-character record:
      Visual form: (white parallelogram)  Name: WHITE PARALLELOGRAM
      Encoding: U+25B1 (decimal 9649)
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
    j = Judge('Wolfram Alpha--28', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_unicode_hollow_parallelogram_input_query", queried_with_all(t, must_all=['unicode', '9632', '9650'], any_of=[], forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'identify the character', 'represents a hollow parallelogram', 'unicode range 9632', 'hollow parallelogram in unicode']) or queried_with_all(t, must_all=['unicode', '9649'], any_of=[], forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to']), f"input_queries={input_queries(t)[:6]}")
    j.check("answer_white_parallelogram", contains_any(fa, ["9649", "25b1"]) and contains_any(fa, ["whiteparallelogram", "▱", "parallelogram"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
