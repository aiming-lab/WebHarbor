#!/usr/bin/env python3
"""Craigslist--4: compare the Berkeley BART studio (id 21) with the quiet San Mateo studio (id 27);
which has the lower rent per square foot. GT: Berkeley ($2195/510 = $4.30/sqft) is lower than San
Mateo ($2350/430 = $5.47/sqft)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, opened_listing, contains_any,
                        llm_text_match, Judge, parse_args)
def main():
    a = parse_args(); j = Judge('Craigslist--4', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_both_studios", opened_listing(t, 21) and opened_listing(t, 27),
            "expected both the Berkeley (id 21) and San Mateo (id 27) studios")
    j.check("answer_berkeley", contains_any(fa, ["berkeley"]),
            f"expected the Berkeley studio as lower rent/sqft; final={fa!r}")
    ok, ev = llm_text_match(fa, "the Berkeley BART studio has the lower rent per square foot "
                            "($4.30/sqft vs the San Mateo studio's $5.47/sqft)",
                            "Which studio has the lower rent per square foot?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()
if __name__ == "__main__":
    main()
