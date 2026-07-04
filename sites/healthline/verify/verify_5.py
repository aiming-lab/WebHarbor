#!/usr/bin/env python3
"""Healthline--5: metformin serious (rare) side effect involving acid buildup in the blood.
GT: lactic acidosis.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_any,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('Healthline--5', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_drug", navigated_to(t, "/drug/metformin"), "expected the metformin drug page")
    j.check("answer_lactic_acidosis", contains_any(fa, ["lactic acidosis"]),
            f"expected 'lactic acidosis'; final={fa!r}")
    ok, ev = llm_text_match(fa, "lactic acidosis (a rare but serious buildup of acid in the blood)",
                            "Which serious rare side effect of metformin involves acid buildup in the blood?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
