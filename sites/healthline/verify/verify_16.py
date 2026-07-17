#!/usr/bin/env python3
"""Healthline--16: compare lisinopril vs atorvastatin — which is the ACE inhibitor, which is the
statin, and what each treats. GT: lisinopril = ACE inhibitor (high blood pressure /
hypertension); atorvastatin = statin (high cholesterol). Requires opening both drug pages.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_all,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('Healthline--16', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_lisinopril", navigated_to(t, "/drug/lisinopril"), "expected the lisinopril page")
    j.check("nav_atorvastatin", navigated_to(t, "/drug/atorvastatin"), "expected the atorvastatin page")
    j.check("answer_classes", contains_all(fa, ["ACE inhibitor", "statin"]),
            f"expected both drug classes named; final={fa!r}")
    ok, ev = llm_text_match(fa, "lisinopril is the ACE inhibitor (treats high blood pressure); "
                            "atorvastatin is the statin (treats high cholesterol)",
                            "Which is the ACE inhibitor vs the statin, and what does each treat?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
