#!/usr/bin/env python3
"""Craigslist--10: jobs — speech language pathologist school-year role; report compensation range,
setting, and required license. GT (id 30): $62-$70 per hour; setting K-8; license CA SLP required."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, opened_listing, contains_any, count_matches,
                        llm_text_match, Judge, parse_args)
def main():
    a = parse_args(); j = Judge('Craigslist--10', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_listing", opened_listing(t, 30), "expected the SLP school-year role (id 30)")
    hits = count_matches(fa, ["62", "70", "K-8", "CA SLP", "SLP required", "license"])
    j.check("answer_facts", contains_any(fa, ["62", "70"]) and hits >= 2,
            f"expected $62-$70/hr, K-8, CA SLP required; final={fa!r}")
    ok, ev = llm_text_match(fa, "$62-$70 per hour; setting K-8; license CA SLP required",
                            "Report the compensation range, setting, and required license.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()
if __name__ == "__main__":
    main()
