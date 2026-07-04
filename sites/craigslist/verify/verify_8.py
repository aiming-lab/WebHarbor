#!/usr/bin/env python3
"""Craigslist--8: browse community events, find the Saturday plant swap, report the time and what
attendees should bring. GT: 'Saturday neighborhood plant swap' (id 35): 10:00 AM; bring labeled
plants."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, opened_listing, contains_all, contains_any,
                        llm_text_match, Judge, parse_args)
def main():
    a = parse_args(); j = Judge('Craigslist--8', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_listing", opened_listing(t, 35), "expected the Saturday plant swap (id 35)")
    j.check("answer_time_bring", contains_any(fa, ["10:00", "10 am", "10am"]) and
            contains_all(fa, ["labeled plants"]) or contains_any(fa, ["labeled plant"]),
            f"expected time 10:00 AM and 'labeled plants'; final={fa!r}")
    ok, ev = llm_text_match(fa, "10:00 AM; bring labeled plants",
                            "What time is the Saturday plant swap and what should attendees bring?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()
if __name__ == "__main__":
    main()
