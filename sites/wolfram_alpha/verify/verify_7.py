#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--7.

Task: Give the final angle and final length after 6s of a Spring pendulum with spring equilibrium length=0.12m, initial length=0.24m, initial angle=80deg, mass=1kg, spring constant=120 N/m .

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=spring pendulum equilibrium=0.12m initial length=0.24m
    angle=80 mass=1kg k=120 (parsed 'SpringPendulum[l0=0.12, l=0.24,
    theta=80 deg, m=1, k=120, t=6]') renders:
      Final angle:  = -73.26 deg  (= -1.279 rad)
      Final length: = 25.21 cm  (= 0.2521 m, 9.925 in, 0.8271 ft)
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
    j = Judge('Wolfram Alpha--7', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_spring_pendulum_input_query",
          queried_with_all(t, must_all=['0.12', '0.24'],
                          any_of=[['springpendulum', 'spring-pendulum']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'give the final angle and final length', 'give the final angle', 'final length after 6s of a spring', 'with spring equilibrium length=0.12', 'final angle and length', 'final length and angle']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_final_angle_and_length", decimal_in(fa, "73.26") and (decimal_in(fa, "25.21") or decimal_in(fa, "0.2521")), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
