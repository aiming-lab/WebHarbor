#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--39.

Task: "Search the title 'GPT-4 Technical Report' and access this paper through
HTML format. Read the paper on this page and tell me what is 'one of the main
goals of developing such models' mentioned in the Introduction."

The paper's HTML rendering (/html/2303.08774, served locally) states in the
Introduction: "One of the main goals of developing such models is to improve
their ability to understand and generate natural language text, particularly
in more complex and nuanced scenarios."

Checks (deterministic):
  nav:    the paper's /html page
  answer: states the main-goals phrase ("understand and generate natural
          language"; hyphen/whitespace normalised, so a correct paraphrase
          like "natural-language text" is accepted)
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, norm_loose, navigated_to,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("ArXiv--39", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_gpt4_html_page", navigated_to(t, "/html/2303.08774"),
            f"urls={[u for u in [s.get('url','') for s in t.get('steps', [])] if '2303.08774' in u][:4]}")
    f = norm_loose(fa)
    j.check("answer_main_goals_phrase",
            "understand and generate natural language" in f,
            f"final={fa[:260]!r}")
    j.emit()


if __name__ == "__main__":
    main()
