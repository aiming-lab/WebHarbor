#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--30.

Task: "Look up the submission guidelines on ArXiv for submitting a paper and
tell me the formats for figures."

The /help/figures page (Figure Formats for Submissions) lists: PDF (vector),
PNG (raster/photos), JPG/JPEG (photos), EPS (deprecated, converted to PDF);
SVG and GIF are not supported.

Checks (deterministic):
  nav:    a /help page (the submission/figures help section)
  answer: pdf + png + (jpg|jpeg) + eps
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_any,
                        contains_all, Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("ArXiv--30", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_help_pages", navigated_to(t, "/help"),
            f"urls={[u for u in [s.get('url','') for s in t.get('steps', [])] if '/help' in u][:4]}")
    j.check("answer_pdf_png",
            contains_all(fa, ["pdf", "png"]), f"final={fa[:240]!r}")
    j.check("answer_jpg_jpeg",
            contains_any(fa, ["jpg", "jpeg"]), f"final={fa[:240]!r}")
    j.check("answer_eps", "eps" in fa.lower(), f"final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
