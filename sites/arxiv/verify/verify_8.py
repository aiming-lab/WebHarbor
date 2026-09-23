#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--8.

Task: "What is the latest news on ArXiv?"

The /news page's latest item (2026-04-05) is "arXiv reaches 3 million
submissions" — newer than every /blog post, so the answer must come from /news.

Checks (deterministic):
  nav:    the /news page
  answer: the 3-million-submissions milestone (3/three million + submissions)
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_any,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("ArXiv--8", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_news_page", navigated_to(t, "/news"),
            f"urls={[u for u in t.get('steps', []) and [s.get('url','') for s in t['steps']] if '/news' in u or '/blog' in u][:4]}")
    f = fa.lower()
    million = ("3 million" in f) or ("three million" in f)
    j.check("answer_latest_news_3m_submissions", million,
            f"final={fa[:220]!r}")
    j.check("answer_about_submissions",
            contains_any(fa, ["submission", "submitted", "article", "scholarly"]),
            f"final={fa[:220]!r}")
    j.emit()


if __name__ == "__main__":
    main()
