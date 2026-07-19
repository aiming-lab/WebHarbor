#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--2.

Among California wilderness permits, find the listing whose detail page combines a
Fishing activity pill with a Trailhead Entry listing detail. Ground truth (unique):
Inyo National Forest Wilderness Permits, parent area Inyo National Forest.

Checks (deterministic first):
nav Inyo permit detail | answer names the permit (and its parent area is contained in the name)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_all,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('RecreationGov--2', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_inyo_permit", navigated_to(t, "inyo-national-forest-wilderness-permits"),
            f"navigated={navigated_to(t, 'inyo-national-forest-wilderness-permits')}")
    j.check("answer_permit_name", contains_all(fa, ["Inyo National Forest Wilderness Permits"]),
            f"answer={fa!r}")
    ok, why = llm_text_match(fa,
        "The permit is 'Inyo National Forest Wilderness Permits' and its parent area is 'Inyo National Forest'.",
        "Report the permit name and its parent area.")
    j.check("llm_name_and_parent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
