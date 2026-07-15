#!/usr/bin/env python3
"""Deterministic verifier for OSU task Ohio State University--13.

Mathematics department chair -> James Cogdell.

Checks (deterministic first; the LLM screenshot check is an anchored confirmation
that is fully skipped under --no_llm):
  nav /departments/department-of-mathematics | answer (ground truth hardcoded here) | screenshot shows the fact
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
    j = Judge("Ohio State University--13", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    nav_ok = navigated_to(t, "/departments/department-of-mathematics")
    j.check("nav_math_dept", nav_ok, f"urls_matched={nav_ok}")
    j.check("answer_cogdell", contains_all(fa, ["James", "Cogdell"]),
            f"final={fa!r}")
    if not a.no_llm:
        s = shot_after_url(t, "/departments/department-of-mathematics") or last_shot(t)
        if s:
            ok, ev = llm_screenshot_shows(s,
                "Chair James Cogdell",
                "Find the chair of the Department of Mathematics at Ohio State.")
            j.check("screenshot_confirms", ok, ev, llm=True)
        else:
            j.check("screenshot_confirms", False, "no screenshots in run", llm=True)
    j.emit()

if __name__ == "__main__":
    main()
