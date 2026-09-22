#!/usr/bin/env python3
"""Healthline--11: via Drugs A-Z, open sertraline (Mental Health Meds) and report its typical
starting dose. GT: 50 mg once daily.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (affirmed_any, number_affirmed, resolve_db, load_run, final_answer, navigated_to, amount_with_unit, llm_text_match, Judge, parse_args, run)

def main():
    a = parse_args(); j = Judge('Healthline--11', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_drug", navigated_to(t, "/drug/sertraline"),
            "expected the sertraline drug page (not just the Drugs A-Z browse)")
    j.check("answer_dose", number_affirmed(fa, 50) and affirmed_any(fa, ["mg", "milligram"]),
            f"expected an affirmed standalone 50 mg dose; final={fa!r}")
    ok, ev = llm_text_match(fa, "50 mg once daily (typical starting dose)",
                            "What is sertraline's typical recommended starting dose?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.check_screenshots(t)
    _init = resolve_db(a.initial_db, a.container, "instance_seed")
    _after = resolve_db(a.after_db, a.container, "instance")
    j.check_readonly(_init, _after)
    j.emit()

if __name__ == '__main__':
    run(main, 'Healthline--11')
