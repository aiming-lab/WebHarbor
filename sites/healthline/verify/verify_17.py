#!/usr/bin/env python3
"""Healthline--17: Heart Health condition often called the 'silent killer' (no symptoms) + what
its overview says you can use to detect it. GT: High Blood Pressure (hypertension); detected with
a simple measurement (a blood-pressure measurement/reading).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (affirmed_any, pair_affirmed, resolve_db, load_run, final_answer, navigated_to, contains_any, llm_text_match, Judge, parse_args, run)

def main():
    a = parse_args(); j = Judge('Healthline--17', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_condition", navigated_to(t, "/condition/hypertension"),
            "expected the High Blood Pressure (hypertension) condition page")
    # The task asks *which* condition this is and how its overview says it can be
    # detected; the answer does not have to repeat the "silent killer" nickname, but it
    # must name the condition and must not deny the detection method.
    j.check("answer_condition", affirmed_any(fa, ["high blood pressure", "hypertension"]),
            f"expected the condition (high blood pressure / hypertension); final={fa!r}")
    j.check("answer_detect", pair_affirmed(fa, "detect", "measure")
            or (affirmed_any(fa, ["measurement", "measur", "monitor", "cuff"])
                and affirmed_any(fa, ["detect", "check", "reading"])),
            f"expected the detection method asserted as affirmative; final={fa!r}")
    ok, ev = llm_text_match(fa, "High Blood Pressure (hypertension), the silent killer, detected "
                            "with a simple (blood pressure) measurement",
                            "Which heart condition is the 'silent killer' and how is it detected?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.check_screenshots(t)
    _init = resolve_db(a.initial_db, a.container, "instance_seed")
    _after = resolve_db(a.after_db, a.container, "instance")
    j.check_readonly(_init, _after)
    j.emit()

if __name__ == '__main__':
    run(main, 'Healthline--17')
