#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--4.

Browse Alaska inventory (Explore By State) and find the Sitka reservable cabin whose
detail page lists both Boat Access and Wood Stove. Ground truth (unique): Hemlock Cabin.

Checks (deterministic first):
nav Hemlock Cabin detail | answer names Hemlock Cabin
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_all,
                        Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('RecreationGov--4', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_hemlock_cabin", navigated_to(t, "hemlock-cabin"),
            f"navigated={navigated_to(t, 'hemlock-cabin')}")
    j.check("answer_hemlock_cabin", contains_all(fa, ["Hemlock Cabin"]), f"answer={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
