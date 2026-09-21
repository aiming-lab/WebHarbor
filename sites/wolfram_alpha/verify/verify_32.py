#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--32.

Task: Print all prime numbers between 1000 and 1200 using Wolfram alpha.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    The verbatim wording hits the generic 'prime numbers' record; the
    computation record needs /input?i=prime numbers between 1000 and 1200
    (parsed 'Primes[{1000, 1200}]') which renders the Result pod:
      1009, 1013, 1019, 1021, 1031, 1033, 1039, 1049, 1051, 1061,
      1063, 1069, 1087, 1091, 1093, 1097, 1103, 1109, 1117, 1123,
      1129, 1151, 1153, 1163, 1171, 1181, 1187, 1193
    and the Length-of-data pod: 28 items.
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
    j = Judge('Wolfram Alpha--32', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_primes_range_input_query",
          queried_with_all(t, must_all=['1000', '1200'],
                          any_of=[['prime']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'print all prime numbers', 'all prime numbers between 1000']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_prime_list_coverage", count_named(fa, ['1009', '1013', '1019', '1021', '1031', '1033', '1039', '1049', '1051', '1061', '1063', '1069', '1087', '1091', '1093', '1097', '1103', '1109', '1117', '1123', '1129', '1151', '1153', '1163', '1171', '1181', '1187', '1193']) >= 12 and decimal_in(fa, "1009") and decimal_in(fa, "1193"), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
