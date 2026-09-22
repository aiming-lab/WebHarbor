#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--35.

Task: "Retrieve the latest research paper in Quantum Physics from ArXiv and
provide the title, author(s), and date of submission."

The quant-ph listing's newest papers (both 2026-04-28, top entry first) are
hardcoded below.

Checks (deterministic):
  nav:    a quant-ph listing/search URL or a candidate /abs page
  answer: names one of the two newest quant-ph papers + >=2 author names + the
          date 2026-04-28
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, norm, has_date,
                        paper_mentioned, navigated_to, Judge, parse_args)

# (arxiv_id, title, author surname tokens)
CANDIDATES = [
    ("2604.40002", "Variational quantum eigensolvers for strongly correlated electrons",
     ["nielsen", "chuang", "kitaev"]),
    ("2604.40001", "Error-corrected quantum computing with neutral atom arrays",
     ["preskill", "aaronson", "arute", "nielsen"]),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--35", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    matched = next((c for c in CANDIDATES if paper_mentioned(fa, c[0], c[1])), None)
    j.check("answer_names_latest_quantph_paper", matched is not None,
            f"final={fa[:240]!r}")
    nav_ok = (any("quant-ph" in u for u in urls)
              or (matched and navigated_to(t, f"/abs/{matched[0]}")))
    j.check("nav_quantph", nav_ok,
            f"urls={[u for u in urls if 'quant' in u][:4]}")
    j.check("answer_date_2026_04_28", has_date(fa, "2026-04-28"),
            f"final={fa[:240]!r}")
    if matched is None:
        j.emit()
    aid, title, surnames = matched
    f = norm(fa)
    found = [s for s in surnames if s in f]
    j.check("answer_authors", len(found) >= 2, f"found={found} final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
