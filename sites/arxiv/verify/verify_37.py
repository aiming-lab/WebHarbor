#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--37.

Task: "Find the names of people in ArXiv's Leadership Team."

The /about page lists the 7-person Leadership Team: Ramin Zabih (Faculty
Director), Stacy Konkiel, Steinn Sigurdsson, Charles Frankston, Jake Weiskoff,
Laurinda Demers, Alison Fromme.

Checks (deterministic):
  nav:    the /about page
  answer: all seven names
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, norm, contains_all,
                        navigated_to, Judge, parse_args)

LEADERSHIP = ["ramin zabih", "stacy konkiel", "steinn sigurdsson",
              "charles frankston", "jake weiskoff", "laurinda demers",
              "alison fromme"]


def main():
    a = parse_args()
    j = Judge("ArXiv--37", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_about", navigated_to(t, "/about"),
            f"urls={[u for u in [s.get('url','') for s in t.get('steps', [])] if '/about' in u][:4]}")
    f = norm(fa)
    missing = [n for n in LEADERSHIP if n not in f]
    j.check("answer_all_seven_names", not missing,
            f"missing={missing} final={fa[:300]!r}")
    j.emit()


if __name__ == "__main__":
    main()
