#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--36.

Task: "Search 'CVPR 2023' and 'CVPR2023' through journal ref on ArXiv to see how
many results there are respectively."

A journal-ref search for "CVPR 2023" returns 4 results; "CVPR2023" returns 3
results (the site's advanced search offers the Journal-ref field).

Checks (deterministic):
  nav:    journal-ref search URLs for both spellings
  answer: reports both totals (4 and 3) and mentions the CVPR query
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, has_number,
                        Judge, parse_args)

SPACED_RESULTS = 4
NOSPACE_RESULTS = 3


def main():
    a = parse_args()
    j = Judge("ArXiv--36", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_spaced = any("journal_ref" in u and ("cvpr+2023" in u or "cvpr%202023" in u
                                             or "cvpr%2b2023" in u) for u in urls)
    nav_nospace = any("journal_ref" in u and "cvpr2023" in u for u in urls)
    j.check("nav_journal_ref_cvpr_2023", nav_spaced,
            f"urls={[u for u in urls if 'journal' in u][:4]}")
    j.check("nav_journal_ref_cvpr2023", nav_nospace,
            f"urls={[u for u in urls if 'journal' in u][:4]}")
    j.check("answer_mentions_cvpr", "cvpr" in fa.lower(), f"final={fa[:200]!r}")
    j.check("answer_4_spaced_results", has_number(fa, SPACED_RESULTS),
            f"final={fa[:260]!r}")
    j.check("answer_3_nospace_results", has_number(fa, NOSPACE_RESULTS),
            f"final={fa[:260]!r}")
    j.emit()


if __name__ == "__main__":
    main()
