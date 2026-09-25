#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--33.

Task: "Query ArXiv for the latest research article in the category of Systems
and Control under Computer Science. Summarize the main objective or hypothesis
presented in the paper and provide the names of the authors."

The cs.SY listing (which cross-lists eess.SY) has its newest entries on
2026-04-28; the top entry is arXiv:2604.71175 "Data-driven model predictive
control of HVAC systems" (authors Pang, Xiuling; Leclerc, Yannick), whose
abstract states the main objective and hypothesis explicitly. The same-day
alternatives are hardcoded below.

Checks (deterministic):
  nav:    a cs.SY/eess.SY listing URL or a candidate /abs page
  answer: names one of the newest Systems-and-Control papers + both authors +
          >=2 objective keywords from that paper's abstract
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, norm, contains_all,
                        paper_mentioned, navigated_to, Judge, parse_args)

# (arxiv_id, title, author surname tokens, objective keywords)
CANDIDATES = [
    ("2604.71175", "Data-driven model predictive control of HVAC systems",
     ["pang", "leclerc"],
     ["model predictive control", "hvac", "energy consumption", "comfort", "30%"]),
    ("2604.54152", "End-to-end control for autonomous vehicles via reinforcement learning",
     ["okafor", "tanaka"],
     ["reinforcement learning", "autonomous vehicles", "carla", "end-to-end"]),
    ("2604.39694", "Autonomous vehicles perception in adverse weather conditions",
     ["silva", "wang"],
     ["perception", "adverse weather", "rain", "snow", "fusion"]),
    ("2604.08327", "Finite-time Reachability for Constrained, Partially Uncontrolled Nonlinear Systems",
     ["haddad", "schmidt", "ivanov"],
     ["finite time", "reachability", "constrained nonlinear system", "target state"]),
]


def main():
    a = parse_args()
    j = Judge("ArXiv--33", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    matched = next((c for c in CANDIDATES if paper_mentioned(fa, c[0], c[1])), None)
    j.check("answer_names_latest_sy_paper", matched is not None,
            f"final={fa[:240]!r}")
    nav_ok = (any("cs.sy" in u or "eess.sy" in u for u in urls)
              or (matched and navigated_to(t, f"/abs/{matched[0]}")))
    j.check("nav_sy_listing", nav_ok,
            f"urls={[u for u in urls if 'sy' in u][:4]}")
    if matched is None:
        j.emit()
    aid, title, surnames, keywords = matched
    f = norm(fa)
    authors_ok = all(s in f for s in surnames)
    j.check("answer_author_names", authors_ok,
            f"need={surnames} final={fa[:240]!r}")
    j.check("answer_main_objective",
            contains_all(fa, keywords[:2]),
            f"keywords={keywords[:2]} final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
