#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--17.

Task: "Find the paper 'GPT-4 Technical Report', when was v3 submitted?"

The paper's abstract page (/abs/2303.08774) shows the submission history:
[v1] 2023-03-15; [v2] 2023-03-16; [v3] 2023-03-27; [v4] 2023-12-19.

Checks (deterministic):
  nav:    the paper's /abs page
  answer: a v3 marker AND the date 2023-03-27 (any common format)
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, has_date, navigated_to,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("ArXiv--17", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_gpt4_abs_page", navigated_to(t, "/abs/2303.08774"),
            f"urls={[u for u in [s.get('url','') for s in t.get('steps', [])] if '2303.08774' in u][:4]}")
    f = fa.lower()
    v3_marker = ("v3" in f) or ("version 3" in f) or ("third version" in f)
    j.check("answer_marks_v3", v3_marker, f"final={fa[:240]!r}")
    j.check("answer_v3_date_2023_03_27", has_date(fa, "2023-03-27"),
            f"dates={has_date(fa, '2023-03-27')} final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
