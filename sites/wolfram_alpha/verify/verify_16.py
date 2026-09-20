#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--16.

Task: Weight lose for a male with current weight 90 kg, 40 year old, 175 cm. If he intakes 1500 calories every day, how long will it take to lose 17 kg.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=weight loss 90 kg 40 yr 175 cm 1500 cal -17 kg (parsed
    'weight loss | male | 90 kg | 40 yr | 175 cm | 1500 Cal/day | target
    loss 17 kg') renders the Weight-loss-regimen-duration pod:
      3 months 6 days  (= 96 days)
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
    j = Judge('Wolfram Alpha--16', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_weight_loss_input_query",
          queried_with_all(t, must_all=['90', '17', '1500'],
                          any_of=[['weight loss', 'weightloss', 'lose weight', 'weight lose']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'weight lose for a male', 'if he intakes', 'how long will he take', '1500 calories every day']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_weight_loss_duration", (contains_any(fa, ["3 months", "3months", "3 month"]) and contains_any(fa, ["6 days", "6days", "6 day"])) or decimal_in(fa, "96"), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
