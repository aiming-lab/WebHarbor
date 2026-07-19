#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--10.

Use Tickets & Tours to find the Minnesota listing whose detail page includes Accessible
Seating instead of Accessible Route. Ground truth (unique in MN): Voyageurs National Park
Tours, parent area Voyageurs National Park.

Checks (deterministic first):
nav Voyageurs Tours detail | answer names the listing (parent area is contained in the name)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_all,
                        Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('RecreationGov--10', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_voyageurs_tours", navigated_to(t, "voyageurs-national-park-tours"),
            f"navigated={navigated_to(t, 'voyageurs-national-park-tours')}")
    j.check("answer_listing", contains_all(fa, ["Voyageurs National Park Tours"]), f"answer={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
