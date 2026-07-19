#!/usr/bin/env python3
"""Deterministic verifier for GOV.UK--15.

Service used to book your driving test.
Ground truth: the "Book your driving test" service (practical test; requires a
passed theory test). Navigation task — reaching the service page is the objective.

Checks: nav to the book-your-driving-test page + answer references booking the
(practical) driving test + anchored LLM consistency.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any,
                        llm_text_match, Judge, parse_args)

SLUG = "/guidance/book-your-driving-test"
QUES = "Find the service used to book your driving test."

def main():
    a = parse_args()
    j = Judge('GOV.UK--15', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_driving_test", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_service", contains_any(fa, ["book your driving test", "driving test"]), f"answer={fa!r}")
    ok, why = llm_text_match(fa, "The 'Book your driving test' service", QUES)
    j.check("llm_consistent", ok, why, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
