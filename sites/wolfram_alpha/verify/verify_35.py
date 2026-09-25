#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--35.

Task: Calculate the determinant of a 6x6 Hilbert matrix.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=determinant of 6 by 6 Hilbert matrix (parsed
    'Det[HilbertMatrix[6]]') renders:
      Exact: 1 / 186313420339200000
      Decimal: = 5.3673 x 10^-18
      Condition number: kappa(H_6) = 1.495 x 10^7
    The abbreviated forms also render the same record with the
    Determinant pod (browser-probed): 'det of 6 by 6 Hilbert
    matrix', 'Det[HilbertMatrix[6]]', 'det HilbertMatrix[6]'
    (all parsed 'HilbertMatrix[6]').
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
    j = Judge('Wolfram Alpha--35', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_hilbert_determinant_input_query",
          queried_with_all(t, must_all=['hilbert'],
                          any_of=[['determinant', 'det'], ['6x6', '6by6', '6-by-6', '6*6', 'hilbertmatrix[6]', 'hilbertmatrix(6)', 'hilbertmatrix6', 'hilbertmatrix{6}']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'calculate the determinant of a 6x6']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_hilbert_determinant", contains_any(fa, ["186313420339200000"]) or (decimal_in(fa, "5.3673", tol=0.0005) and  contains_any(fa, ["10^-18", "e-18"])), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
