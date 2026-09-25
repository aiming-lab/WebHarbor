#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--41.

Task: "Find the button to share arxiv non-profit store and follow the QR code to
share the shop. Then add arXiv Forever short sleeve (XL) to your cart."

The store item page /store/arxiv-forever-short-sleeve offers style "Unisex XL"
and an Add to Cart button.

NOTE (quality audit): the mirror has no share button, no QR code, and no cart
state — Add to Cart is a JS alert only, so no DB row records it. The grading
contract below anchors the verifiable part: reaching the arXiv Forever Short
Sleeve item page and reporting the XL add-to-cart action.

Checks (deterministic):
  nav:    the arXiv Forever Short Sleeve item page
  answer: mentions XL AND the cart action
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, Judge,
                        parse_args)


def main():
    a = parse_args()
    j = Judge("ArXiv--41", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_forever_sleeve_item",
            navigated_to(t, "/store/arxiv-forever-short-sleeve"),
            f"urls={[u for u in [s.get('url','') for s in t.get('steps', [])] if '/store' in u.lower()][:4]}")
    xl = bool(re.search(r"\bXL\b", fa))
    j.check("answer_selects_xl", xl, f"final={fa[:240]!r}")
    j.check("answer_add_to_cart", "cart" in fa.lower(), f"final={fa[:240]!r}")
    j.emit()


if __name__ == "__main__":
    main()
