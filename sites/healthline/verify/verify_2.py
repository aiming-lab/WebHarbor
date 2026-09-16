#!/usr/bin/env python3
"""Healthline--2: lisinopril typical starting dose for hypertension. GT: 10 mg once daily."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (claim_affirmed, affirmed_any, resolve_db, load_run, final_answer, navigated_to, contains_any, llm_text_match, Judge, parse_args, run)
def main():
    a = parse_args(); j = Judge('Healthline--2', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_drug", navigated_to(t, "/drug/lisinopril"), "expected the lisinopril drug page")
    j.check("answer_dose", claim_affirmed(fa, "10 mg") or claim_affirmed(fa, "10mg"),
            f"expected an affirmed 10 mg dose; final={fa!r}")
    ok, ev = llm_text_match(fa, "10 mg once daily (typical starting dose for hypertension)",
                            "What is lisinopril's typical starting dose for hypertension?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.check_screenshots(t)
    _init = resolve_db(a.initial_db, a.container, "instance_seed")
    _after = resolve_db(a.after_db, a.container, "instance")
    j.check_readonly(_init, _after)
    j.emit()
if __name__ == '__main__':
    run(main, 'Healthline--2')
