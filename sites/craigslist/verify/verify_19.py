#!/usr/bin/env python3
"""Craigslist--19: furniture — the white standing desk frame in Palo Alto; report the height range
and load rating. GT (id 8): height range 25-50 in; load rating 220 lb."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, opened_listing, contains_any,
                        llm_text_match, Judge, parse_args)
def main():
    a = parse_args(); j = Judge('Craigslist--19', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_listing", opened_listing(t, 8), "expected the white standing desk frame (id 8)")
    j.check("answer_height", contains_any(fa, ["25-50", "25 - 50", "25 to 50"]),
            f"expected height range 25-50 in; final={fa!r}")
    j.check("answer_load", contains_any(fa, ["220"]), "expected load rating 220 lb")
    ok, ev = llm_text_match(fa, "height range 25-50 in; load rating 220 lb",
                            "Report the standing desk frame's height range and load rating.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()
if __name__ == "__main__":
    main()
