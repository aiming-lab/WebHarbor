#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--18.

Search BLM-managed permits and find the wilderness listing near Winkelman. Ground truth
(unique): Aravaipa Canyon Wilderness Permits. Report one activity (Canyons / Hiking /
Wildlife Viewing) plus whether the listing mentions Day Use Permit, Overnight Permit, or
both — it mentions BOTH.

Checks (deterministic first):
nav Aravaipa Canyon detail | answer names one activity | answer says both permit types
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any, contains_all,
                        Judge, parse_args)

ACTIVITIES = ["Canyons", "Hiking", "Wildlife Viewing"]

def main():
    a = parse_args()
    j = Judge('RecreationGov--18', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    both_ok = contains_all(fa, ["Day Use Permit", "Overnight Permit"])
    j.check("nav_aravaipa", navigated_to(t, "aravaipa-canyon-wilderness-permits"),
            f"navigated={navigated_to(t, 'aravaipa-canyon-wilderness-permits')}")
    j.check("answer_activity", contains_any(fa, ACTIVITIES), f"answer={fa!r}")
    j.check("answer_both_permit_types", both_ok, f"answer={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
