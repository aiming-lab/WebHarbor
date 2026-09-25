#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--5.

Task: "Search papers about \"quantum computing\" which has been submitted to the
Quantum Physics category on ArXiv. How many results in total. What if search in
all archives?"

The site's search for "quantum computing" restricted to the Quantum Physics
category returns 48 results; searching all archives returns 207 results.

Checks (deterministic):
  nav:    a /search URL with both query tokens AND the category=quant-ph filter
  answer: reports both totals (48 and 207) as numbers
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, has_number,
                        Judge, parse_args)

QUANT_PH_RESULTS = 48
ALL_ARCHIVES_RESULTS = 207


def main():
    a = parse_args()
    j = Judge("ArXiv--5", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_quantph = any(
        "/search" in u and "quantum" in u and "computing" in u and "quant-ph" in u
        for u in urls)
    j.check("nav_quantph_filtered_search", nav_quantph,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    j.check("answer_quantph_total_48", has_number(fa, QUANT_PH_RESULTS),
            f"final={fa[:260]!r}")
    j.check("answer_all_archives_total_207", has_number(fa, ALL_ARCHIVES_RESULTS),
            f"final={fa[:260]!r}")
    j.emit()


if __name__ == "__main__":
    main()
