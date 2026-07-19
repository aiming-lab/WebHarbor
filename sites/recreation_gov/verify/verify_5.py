#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--5.

From Explore Most Popular Locations, open Apostle Islands Camping Permits (under
Apostle Islands National Lakeshore). Report one activity shown and whether the listing
is a permit or a campground. Ground truth: activities Island Camping / Kayaking / Lakes;
it is a permit listing.

Checks (deterministic first):
nav Apostle Islands permit detail | answer names one activity | answer says permit
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any,
                        Judge, parse_args)

ACTIVITIES = ["Island Camping", "Kayaking", "Lakes"]

def main():
    a = parse_args()
    j = Judge('RecreationGov--5', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_apostle_islands", navigated_to(t, "apostle-islands-camping-permits"),
            f"navigated={navigated_to(t, 'apostle-islands-camping-permits')}")
    j.check("answer_activity", contains_any(fa, ACTIVITIES), f"answer={fa!r}")
    j.check("answer_permit", contains_any(fa, ["permit"]), f"answer={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
