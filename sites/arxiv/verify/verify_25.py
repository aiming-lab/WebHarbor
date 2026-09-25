#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--25.

Task: "Browse the ArXiv store and let me know how many different types of
merchandise are available."

The store page (/store) lists exactly 7 merchandise products: arXiv Logo
Shirt, arXiv Forever Short Sleeve, arXiv Ceramic Mug, arXiv Canvas Tote Bag,
arXiv Sticker Pack, arXiv Hoodie, arXiv Dot Grid Notebook.

Checks (deterministic):
  nav:    the /store page
  answer: 7 bound to merchandise/product/item/type words
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, counts, navigated_to,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("ArXiv--25", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_store", navigated_to(t, "/store"),
            f"urls={[u for u in [s.get('url','') for s in t.get('steps', [])] if '/store' in u.lower()][:4]}")
    j.check("answer_7_merchandise",
            counts(fa, 7, "merchandise", "product", "products", "item", "items",
                   "piece", "pieces", "type", "types"),
            f"final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
