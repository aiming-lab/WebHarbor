#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--19.

Task: "Which university maintains and manages ArXiv. Accessing the university's
website from ArXiv, how many undergraduate students are currently at the
university."

ArXiv is hosted at Cornell University (the /about page links to the local
Cornell page); /external/cornell lists Undergraduate students: 15,735.

Checks (deterministic):
  nav:    the Cornell page reached from arXiv (and an arXiv page naming Cornell)
  answer: Cornell AND 15,735 undergraduates
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, has_number, navigated_to,
                        navigated_any, Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("ArXiv--19", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_cornell_page", navigated_to(t, "/external/cornell"),
            f"urls={[u for u in [s.get('url','') for s in t.get('steps', [])] if 'cornell' in u.lower()][:4]}")
    nav_source = navigated_any(t, ["/about", "/help/who", "/external/cornell"])
    j.check("nav_arxiv_page_naming_host", nav_source,
            f"final={fa[:200]!r}")
    j.check("answer_cornell", "cornell" in fa.lower(), f"final={fa[:200]!r}")
    j.check("answer_15735_undergrads", has_number(fa, 15735), f"final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
