#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--32.

Task: "Locate the latest paper on ArXiv within the 'Nonlinear Sciences -
Chaotic Dynamics' category, summarize the abstract and note the submission
date."

The nlin.CD listing's newest papers (both 2026-04-09; top entry first) are
hardcoded below with the abstract text the mirror actually serves and the
submission date 2026-04-09.

Checks (deterministic):
  nav:    an nlin.CD listing URL or a candidate /abs page
  answer: names one of the two newest papers + the date 2026-04-09 + >=2
          keywords from that paper's on-mirror abstract (hyphen/whitespace
          normalised matching, so a correct paraphrase like "quantum-chaos"
          is accepted)
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, has_date,
                        paper_mentioned, navigated_to, contains_all_loose,
                        Judge, parse_args)

CANDIDATES = [
    ("2604.12345", "Chaos in driven nonlinear oscillators with memory",
     ["quantum kicked top", "quantum chaos", "qkt", "hilbert space"]),
    ("2604.07003", "Strange Attractors in Nonlinear Delay Differential Equations",
     ["automated negotiation", "llms", "on-device", "computational cost"]),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--32", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    matched = next((c for c in CANDIDATES if paper_mentioned(fa, c[0], c[1])), None)
    j.check("answer_names_latest_nlin_cd_paper", matched is not None,
            f"final={fa[:240]!r}")
    nav_ok = (any("nlin.cd" in u for u in urls)
              or (matched and navigated_to(t, f"/abs/{matched[0]}")))
    j.check("nav_nlin_cd", nav_ok,
            f"urls={[u for u in urls if 'nlin' in u][:4]}")
    j.check("answer_date_2026_04_09", has_date(fa, "2026-04-09"),
            f"final={fa[:240]!r}")
    if matched is None:
        j.emit()
    aid, title, keywords = matched
    j.check("answer_summarises_abstract",
            contains_all_loose(fa, keywords[:2]),
            f"keywords={keywords[:2]} final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
