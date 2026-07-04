#!/usr/bin/env python3
"""Craigslist--1: east bay apartment/studio under $2400 with in-unit laundry — report sqft + pet
policy. GT: 'Sunny studio near Berkeley BART' (id 21): 510 sqft, cats ok (the only east-bay
sub-$2400 listing with in-unit laundry)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, opened_listing, number_mentioned, contains_any,
                        llm_text_match, Judge, parse_args)
def main():
    a = parse_args(); j = Judge('Craigslist--1', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_listing", opened_listing(t, 21), "expected the Berkeley BART studio (id 21)")
    j.check("answer_sqft", number_mentioned(fa, 510), f"expected 510 sqft; final={fa!r}")
    j.check("answer_pets", contains_any(fa, ["cats ok", "cat"]), "expected pet policy 'cats ok'")
    ok, ev = llm_text_match(fa, "510 square feet; pet policy: cats ok",
                            "Report the studio's square footage and pet policy.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()
if __name__ == "__main__":
    main()
