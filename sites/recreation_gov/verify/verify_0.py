#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--0.

Compare Yosemite Creek Campground and Porcupine Flat Campground; the one open for
the featured trip window is Yosemite Creek (available), Porcupine Flat is not.
Report one activity from the open one (Camping / Waterfalls / Hiking).

Checks (deterministic first; LLM anchored on ground truth):
nav both detail pages | answer names Yosemite Creek | answer names one of its activities
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

ACTIVITIES = ["Camping", "Waterfalls", "Hiking"]

def main():
    a = parse_args()
    j = Judge('RecreationGov--0', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_yosemite_creek", navigated_to(t, "yosemite-creek-campground"),
            f"navigated={navigated_to(t, 'yosemite-creek-campground')}")
    j.check("nav_porcupine_flat", navigated_to(t, "porcupine-flat-campground"),
            f"navigated={navigated_to(t, 'porcupine-flat-campground')}")
    j.check("answer_names_open", contains_any(fa, ["Yosemite Creek"]), f"answer={fa!r}")
    j.check("answer_activity", contains_any(fa, ACTIVITIES), f"answer={fa!r}")
    ok, why = llm_text_match(fa,
        "Yosemite Creek Campground is the one open for the featured window (Porcupine Flat is unavailable); "
        "its activities are Camping, Waterfalls, Hiking.",
        "Which of the two campgrounds is open, and one activity from it?")
    j.check("llm_open_and_activity", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
