#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--12.

Task: "Find store in arXiv Help, tell me how many styles of arXiv Logo Shirt
are available?"

The arXiv Logo Shirt store item (/store/arxiv-logo-shirt) lists exactly 4
styles: Unisex short sleeve, Women's short sleeve, Unisex long sleeve, Women's
long sleeve.

Checks (deterministic):
  nav:    the store (or its help page / the shirt's item page)
  answer: 4 bound to styles
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, counts, navigated_to,
                        navigated_any, Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("ArXiv--12", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    nav_store = (navigated_to(t, "/store")
                 or navigated_to(t, "/store/arxiv-logo-shirt")
                 or navigated_to(t, "/help/store"))
    j.check("nav_store_or_logo_shirt", nav_store,
            f"urls={[u for u in [s.get('url','') for s in t.get('steps', [])] if 'store' in u.lower()][:4]}")
    j.check("answer_4_styles", counts(fa, 4, "style", "styles"),
            f"final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
