#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--16.

Task: "Locate the latest research about gravitational waves that were uploaded
to ArXiv this week and provide a brief summary of one article's main findings."

The site pins "today" at 2026-04-28; "this week" is the last-7-days window. The
gravitational-wave papers uploaded in that window are hardcoded below with their
abstracts as served by the mirror; the newest is arXiv:2604.43728.

Checks (deterministic):
  nav:    a gravitational search URL or a candidate /abs page
  answer: names one of this week's gravitational-wave papers AND summarises it
          (>=2 keywords from that paper's abstract)
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, norm,
                        paper_mentioned, navigated_to, contains_all,
                        Judge, parse_args)

# (arxiv_id, title, abstract keywords)
CANDIDATES = [
    ("2604.43728", "Detection of continuous gravitational waves from a spinning neutron star",
     ["240 hz", "neutron star", "1.4 solar masses", "accretion-powered"]),
    ("2604.66389", "Gravitational waves from neutron star cores and the equation of state",
     ["neutron star", "equation of state"]),
    ("2604.40626", "Binary black hole merger catalog from LIGO O5",
     ["18 binary black hole", "ligo o5", "intermediate-mass"]),
    ("2604.76449", "Gravitational wave background from primordial black holes",
     ["stochastic", "primordial black holes", "early universe"]),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--16", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = (any("/search" in u and "gravitational" in u for u in urls)
              or any(navigated_to(t, f"/abs/{aid}") for aid, _, _ in CANDIDATES))
    j.check("nav_gravitational_search", nav_ok,
            f"urls={[u for u in urls if '/search' in u][:4]}")
    matched = next(
        (c for c in CANDIDATES if paper_mentioned(fa, c[0], c[1])), None)
    j.check("answer_names_weekly_gw_paper", matched is not None,
            f"final={fa[:240]!r}")
    if matched is None:
        j.emit()
    aid, title, keywords = matched
    j.check("answer_summarises_main_findings",
            contains_all(fa, keywords[:2]),
            f"keywords={keywords[:2]} final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
