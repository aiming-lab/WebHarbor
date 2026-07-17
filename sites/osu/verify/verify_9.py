#!/usr/bin/env python3
"""Deterministic verifier for OSU task Ohio State University--9.

Engineering degree types -> BS, MS, PhD (at least two required).

Checks (deterministic first; the LLM screenshot check is an anchored confirmation
that is fully skipped under --no_llm):
  nav /programs | answer (ground truth hardcoded here) | screenshot shows the fact
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer,
                        last_shot, shot_after_url, contains_all, contains_any,
                        contains_number, count_present, answer_equals,
                        llm_text_match, llm_screenshot_shows, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge("Ohio State University--9", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    nav_ok = navigated_any(t, ["college=engineering", "/programs"])
    j.check("nav_engineering_programs", nav_ok, f"urls_matched={nav_ok}")
    j.check("answer_engineering_degrees_2plus", (contains_any(fa, ["BS", "B.S.", "bachelor"]) + contains_any(fa, ["MS", "M.S.", "master"]) + contains_any(fa, ["phd", "ph.d", "doctor", "doctoral"])) >= 2,
            f"final={fa!r}")
    if not a.no_llm:
        s = shot_after_url(t, "/programs") or last_shot(t)
        if s:
            ok, ev = llm_screenshot_shows(s,
                "Engineering degree types include BS, MS, and PhD",
                "What degree types are offered in the College of Engineering at Ohio State?")
            j.check("screenshot_confirms", ok, ev, llm=True)
        else:
            j.check("screenshot_confirms", False, "no screenshots in run", llm=True)
    j.emit()

if __name__ == "__main__":
    main()
