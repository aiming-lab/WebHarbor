#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--38.

Task: "Find the ArXiv Blog on the ArXiv website and summarize the content of its
latest article."

The /blog page's latest post is "Open Access in 2026: What's Next for arXiv"
(2026-04-02, arXiv Editorial Team) — newer than the other two posts, so the
answer must be about the open-access roadmap post, not the HTML-rendering or
moderation posts.

Checks (deterministic):
  nav:    the /blog page (or the latest post's page)
  answer: open access + 2026 + a roadmap/theme keyword
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, contains_any, navigated_to,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("ArXiv--38", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_blog", navigated_to(t, "/blog"),
            f"urls={[u for u in [s.get('url','') for s in t.get('steps', [])] if '/blog' in u][:4]}")
    j.check("answer_open_access_2026",
            "open access" in fa.lower() and "2026" in fa,
            f"final={fa[:240]!r}")
    j.check("answer_latest_post_theme",
            contains_any(fa, ["roadmap", "next", "subject area", "subject areas",
                             "partnership", "html", "free", "decade", "editorial"]),
            f"final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
