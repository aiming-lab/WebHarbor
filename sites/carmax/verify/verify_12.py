#!/usr/bin/env python3
"""Verifier for CarMax--12: find the FAQ answer to 'How long is my appraisal offer good
for?' and report the number of days it is valid.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, price_mentioned, contains_any,
                        llm_text_match, Judge, parse_args)

# CarMax appraisal offers are valid 7 days (matches reserve/offer logic: created + 7d).
DAYS = 7

def main():
    a = parse_args()
    j = Judge('CarMax--12', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_faq", navigated_to(t, "/faq"), "expected a /faq page")
    j.check("answer_days", price_mentioned(fa, DAYS) or contains_any(fa, ["7 days", "seven days"]),
            f"expected {DAYS} days; final={fa!r}")
    ok, ev = llm_text_match(fa, f"the appraisal offer is valid for {DAYS} days",
                            "How many days is a CarMax appraisal offer good for?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
