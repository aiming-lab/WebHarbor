#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--28.

Task: "Search 'Poly encoder' by title on ArXiv and check whether the articles
in the search results provide HTML access."

A title search for "Poly encoder" returns no exact matches (the paper is titled
"Poly-encoders"); the all-fields search surfaces arXiv:1905.01969 "Poly-encoders:
Architectures and Pre-training Strategies..." whose result card and abstract
page carry the [html] access link — every article in the results provides HTML
access on this mirror.

Checks (deterministic):
  nav:    a /search URL carrying the poly query
  answer: states HTML access positively (html + available/access/yes) and does
          not deny it
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, contains_any,
                        Judge, parse_args)

NEGATIVE = re.compile(
    r"no html|without html|not available|unavailable|not provide|"
    r"doesn'?t provide|do not provide|lack[s]? html|no html access")


def main():
    a = parse_args()
    j = Judge("ArXiv--28", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = any("/search" in u and "poly" in u for u in urls)
    j.check("nav_poly_search", nav_ok,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    f = fa.lower()
    positive = ("html" in f) and contains_any(
        fa, ["available", "access", "yes", "experimental", "provided", "provide"])
    negative = bool(NEGATIVE.search(f))
    j.check("answer_html_access_available", positive and not negative,
            f"positive={positive} negative={negative} final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
