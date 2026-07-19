#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--7.

Open the "Plan Ahead and Play It Safe for Your Next Outdoor Adventure" article and
report the three checks travelers should make. Ground truth (on-page): the inventory
type you need, the allowed date window, and the agency rules attached to the reservation.

Checks (deterministic first; LLM anchored on ground truth):
nav the article | answer names the three checks (inventory type / date window / agency rules)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, count_present,
                        llm_text_match, Judge, parse_args)

CHECK_TOKENS = ["inventory", "date", "agency"]

def main():
    a = parse_args()
    j = Judge('RecreationGov--7', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_article", navigated_to(t, "play-it-safe-trip-planning"),
            f"navigated={navigated_to(t, 'play-it-safe-trip-planning')}")
    j.check("answer_three_checks", count_present(fa, CHECK_TOKENS) >= 3,
            f"present={count_present(fa, CHECK_TOKENS)}/3 answer={fa!r}")
    ok, why = llm_text_match(fa,
        "The three checks are: the inventory type you need, the allowed date window, and the "
        "agency rules attached to that reservation.",
        "What are the three checks travelers should make before committing to a long drive?")
    j.check("llm_three_checks", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
