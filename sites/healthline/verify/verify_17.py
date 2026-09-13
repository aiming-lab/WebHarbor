#!/usr/bin/env python3
"""Healthline--17: Heart Health condition often called the 'silent killer' (no symptoms) + what
its overview says you can use to detect it. GT: High Blood Pressure (hypertension); detected with
a simple measurement (a blood-pressure measurement/reading).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_any,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('Healthline--17', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_condition", navigated_to(t, "/condition/hypertension"),
            "expected the High Blood Pressure (hypertension) condition page")
    j.check("answer_detect", contains_any(fa, ["measurement", "measur", "blood pressure reading",
                                               "blood pressure check", "monitor", "cuff"]),
            f"expected the detection method (a simple measurement); final={fa!r}")
    ok, ev = llm_text_match(fa, "High Blood Pressure (hypertension), the silent killer, detected "
                            "with a simple (blood pressure) measurement",
                            "Which heart condition is the 'silent killer' and how is it detected?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
