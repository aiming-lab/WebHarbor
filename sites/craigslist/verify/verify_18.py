#!/usr/bin/env python3
"""Craigslist--18: furniture — the Mission District 'Walnut writing desk with two drawers' in SF
under $150; report its width and depth. GT (id 7): width 42 in, depth 22 in."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, opened_listing, contains_any,
                        llm_text_match, Judge, parse_args)
def main():
    a = parse_args(); j = Judge('Craigslist--18', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_listing", opened_listing(t, 7), "expected the Walnut writing desk (id 7)")
    j.check("answer_dims", contains_any(fa, ["42"]) and contains_any(fa, ["22"]),
            f"expected width 42 in and depth 22 in; final={fa!r}")
    ok, ev = llm_text_match(fa, "width 42 in, depth 22 in",
                            "Report the desk's width and depth.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()
if __name__ == "__main__":
    main()
