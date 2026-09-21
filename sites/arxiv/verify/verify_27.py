#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--27.

Task: "On ArXiv, what categories does Economics include, and what are their
abbreviations?"

Economics (econ) includes Econometrics (econ.EM), General Economics (econ.GN)
and Theoretical Economics (econ.TH) — shown by the /category/econ page
(description + sub-category codes) and the /category_taxonomy page.

Checks (deterministic):
  nav:    the econ category page, the taxonomy, or an econ listing/search
  answer: all three subcategory names AND >=2 of the three abbreviations
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, norm, contains_all,
                        Judge, parse_args)

NAMES = ["econometrics", "general economics", "theoretical economics"]
ABBR = ["econ.em", "econ.gn", "econ.th"]


def main():
    a = parse_args()
    j = Judge("ArXiv--27", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = any("/category/econ" in u or "/category_taxonomy" in u
                 or "/list/econ" in u or ("econ" in u and "/search" in u)
                 for u in urls)
    j.check("nav_econ_category", nav_ok,
            f"urls={[u for u in urls if 'econ' in u][:4]}")
    f = norm(fa)
    j.check("answer_three_subcategories",
            contains_all(fa, NAMES), f"final={fa[:260]!r}")
    abbr_found = [x for x in ABBR if x in f]
    j.check("answer_abbreviations", len(abbr_found) >= 2,
            f"found={abbr_found} final={fa[:260]!r}")
    j.emit()


if __name__ == "__main__":
    main()
