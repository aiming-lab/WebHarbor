#!/usr/bin/env python3
"""NVIDIA--3: among the GeForce RTX 50 Series cards, the least expensive one + its price.
Ground truth: GeForce RTX 5060 @ $299. Deterministic: nav to the catalog + answer tokens.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_any,
                        price_mentioned, llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('NVIDIA--3', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_catalog", navigated_to(t, "/products"), "expected the products catalog")
    j.check("answer_names_5060", contains_any(fa, ["5060"]),
            f"expected the RTX 5060; final={fa!r}")
    j.check("answer_price", price_mentioned(fa, 299), "expected price $299")
    ok, ev = llm_text_match(fa, "GeForce RTX 5060 at $299 (the cheapest RTX 50 Series card)",
                            "Which RTX 50 Series card is least expensive and what is its price?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
