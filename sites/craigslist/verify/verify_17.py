#!/usr/bin/env python3
"""Craigslist--17: volunteer bike repair clinic in the east bay; report the time and skill
requirement. GT (id 36): 1:00 PM; skill: basic bike repair."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, opened_listing, contains_any,
                        llm_text_match, Judge, parse_args)
def main():
    a = parse_args(); j = Judge('Craigslist--17', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_listing", opened_listing(t, 36), "expected the volunteer bike repair clinic (id 36)")
    j.check("answer_time", contains_any(fa, ["1:00 pm", "1 pm", "1pm"]), f"expected 1:00 PM; final={fa!r}")
    j.check("answer_skill", contains_any(fa, ["basic bike repair", "bike repair"]),
            "expected skill 'basic bike repair'")
    ok, ev = llm_text_match(fa, "1:00 PM; skill requirement: basic bike repair",
                            "Report the clinic's time and skill requirement.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()
if __name__ == "__main__":
    main()
