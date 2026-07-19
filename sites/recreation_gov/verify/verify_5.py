#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--5.

From Explore Most Popular Locations, open Apostle Islands Camping Permits (under
Apostle Islands National Lakeshore). Report one activity shown and whether the listing
is a permit or a campground. Ground truth: activities Island Camping / Kayaking / Lakes;
it is a permit listing.

Checks (deterministic first; LLM anchored on ground truth):
nav Apostle Islands permit detail | answer names one activity | answer mentions permit
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

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
    # "Is it a permit or a campground" can't be pinned deterministically by banning the
    # substring "campground": a correct answer naturally says something like "it is a
    # permit, not a campground", so that word alone can't be used to fail it. The
    # permit-vs-campground classification is LLM-arbitrated here instead — reliable now
    # that verify_lib SKIPs rather than fail-closes when the LLM is down.
    ok, why = llm_text_match(fa,
        "Apostle Islands Camping Permits is a PERMIT listing (not a campground); its "
        "activities include Island Camping, Kayaking, and Lakes.",
        "Report one activity and whether the listing is a permit or a campground.")
    j.check("llm_permit_classification", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
