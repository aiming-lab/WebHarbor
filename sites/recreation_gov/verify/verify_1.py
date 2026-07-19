#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--1.

Open Point Reyes National Seashore Campground and report two different scenes shown
in the Media Gallery images. Ground-truth gallery: a large oak tree at a campsite,
a campsite with distant Drakes Bay views, and a campsite with picnic table and bear box.

Checks (deterministic first; LLM anchored on ground truth):
nav Point Reyes detail | answer mentions gallery scene content | LLM confirms two distinct scenes
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

SCENE_TOKENS = ["oak", "Drakes Bay", "picnic table", "bear box", "campsite"]

def main():
    a = parse_args()
    j = Judge('RecreationGov--1', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_point_reyes", navigated_to(t, "point-reyes-national-seashore-campground"),
            f"navigated={navigated_to(t, 'point-reyes-national-seashore-campground')}")
    j.check("answer_scene_content", contains_any(fa, SCENE_TOKENS), f"answer={fa!r}")
    ok, why = llm_text_match(fa,
        "The Point Reyes gallery shows: a large oak tree at a campsite; a campsite with distant "
        "views of Drakes Bay; and a campsite with a picnic table and bear box. Any TWO distinct "
        "scenes from these count.",
        "Report two different scenes shown in the Point Reyes campground media gallery.")
    j.check("llm_two_scenes", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
