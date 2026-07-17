#!/usr/bin/env python3
"""Healthline--11: via Drugs A-Z, open sertraline (Mental Health Meds) and report its typical
starting dose. GT: 50 mg once daily.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_any, contains_any,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('Healthline--11', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_drug", navigated_any(t, ["/drug/sertraline", "/drugs"]),
            "expected the Drugs A-Z browse / sertraline page")
    j.check("answer_dose", contains_any(fa, ["50 mg", "50mg"]), f"expected 50 mg; final={fa!r}")
    ok, ev = llm_text_match(fa, "50 mg once daily (typical starting dose)",
                            "What is sertraline's typical recommended starting dose?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
