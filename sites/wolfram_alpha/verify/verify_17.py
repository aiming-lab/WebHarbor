#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--17.

Task: Show the average price of movie ticket in Providence, Nashville, Boise in 2023.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    Three /input queries are needed (each city's record rejects a query
    that names a second city):
      average price of movie ticket Providence 2023 -> mean $14.37 (Q1 $13.44 / Q3 $15.49)
      average price of movie ticket Nashville 2023 -> mean $13.30 (Q1 $12.50 / Q3 $14.61)
      average price of movie ticket Boise 2023     -> mean $11.60 (Q1 $10.81 / Q3 $12.77)
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
    j = Judge('Wolfram Alpha--17', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_movie_ticket_providence_input_query",
          queried_with_all(t, must_all=['providence', 'movie', 'ticket'],
                          any_of=[],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'nashville', 'boise']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("nav_movie_ticket_nashville_input_query",
          queried_with_all(t, must_all=['nashville', 'movie', 'ticket'],
                          any_of=[],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'providence', 'boise']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("nav_movie_ticket_boise_input_query",
          queried_with_all(t, must_all=['boise', 'movie', 'ticket'],
                          any_of=[],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'providence', 'nashville']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_providence_price", bound_nearest(fa, ["providence"], ["14.37"], other_anchors=["nashville", "boise"], other_values=["13.30", "11.60"]), f"final={fa[:200]!r}")
    j.check("answer_nashville_price", bound_nearest(fa, ["nashville"], ["13.30"], other_anchors=["providence", "boise"], other_values=["14.37", "11.60"]), f"final={fa[:200]!r}")
    j.check("answer_boise_price", bound_nearest(fa, ["boise"], ["11.60"], other_anchors=["providence", "nashville"], other_values=["14.37", "13.30"]), f"final={fa[:200]!r}")
    j.check("answer_names_three_cities", contains_any(fa, ["providence"]) and contains_any(fa, ["nashville"]) and contains_any(fa, ["boise"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
