#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--26.

Task: Convert 15 kilograms of sulfuric acid to moles and display the percentage composition of H, S, and O by weight.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=15 kg sulfuric acid to moles percentage H S O composition
    (parsed '15 kg sulfuric acid | basic properties + mass composition')
    renders:
      Molar amount: 153 mol  (M = 98.079 g/mol)
      Composition H: 2.1 %   Composition O: 65.2 %   Composition S: 32.7 %
    ('15 kg sulfuric acid' renders the same moles/composition values).
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
    j = Judge('Wolfram Alpha--26', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_sulfuric_acid_input_query",
          queried_with_all(t, must_all=['15'],
                          any_of=[['sulfuricacid', 'sulfuric acid', 'h2so4']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'convert', 'percent composition', 'percentage composition', 'composition of', 'composition h', 'composition s', 'composition o', 'mass percentage of', 'h2so4 mass percent', 'mass percent h s o', 'h s o moles', 'to moles and display']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_moles_and_composition", decimal_in(fa, "153") and decimal_in(fa, "2.1") and decimal_in(fa, "65.2") and decimal_in(fa, "32.7"), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
