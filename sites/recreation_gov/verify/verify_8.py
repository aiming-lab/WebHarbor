#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--8.

Open the America250 inspiration article and list any three places it mentions.
Ground-truth places on the page: San Francisco Maritime National Historical Park,
Fort Point, Golden Gate, Yosemite, Yellowstone, Denali, Cumberland Island.

Checks (deterministic first):
nav the America250 article | answer names >= 3 of the mentioned places
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, count_present,
                        Judge, parse_args)

PLACES = ["San Francisco Maritime", "Fort Point", "Golden Gate", "Yosemite",
          "Yellowstone", "Denali", "Cumberland Island"]

def main():
    a = parse_args()
    j = Judge('RecreationGov--8', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_america250",
            navigated_to(t, "celebrate-america-250") or navigated_to(t, "1367"),
            f"navigated={navigated_to(t, 'celebrate-america-250')}")
    n = count_present(fa, PLACES)
    j.check("answer_three_places", n >= 3, f"named {n} of the article's places; answer={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
