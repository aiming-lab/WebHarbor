#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--17.

Search Cumberland Island beach camping and open Cumberland Island Camping Permits.
Report the state and one activity. Ground truth: state Georgia (GA); activities
Beach Camping / Wilderness / Wildlife Viewing.

Checks (deterministic first):
nav Cumberland Island permit detail | answer names the state | answer names one activity
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, norm, contains_any,
                        Judge, parse_args)

ACTIVITIES = ["Beach Camping", "Wilderness", "Wildlife Viewing"]

def main():
    a = parse_args()
    j = Judge('RecreationGov--17', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    state_ok = "georgia" in norm(fa) or re.search(r"\bGA\b", fa or "") is not None
    j.check("nav_cumberland", navigated_to(t, "cumberland-island-camping-permits"),
            f"navigated={navigated_to(t, 'cumberland-island-camping-permits')}")
    j.check("answer_state", state_ok, f"answer={fa!r}")
    j.check("answer_activity", contains_any(fa, ACTIVITIES), f"answer={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
