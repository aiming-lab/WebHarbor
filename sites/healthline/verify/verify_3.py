#!/usr/bin/env python3
"""Healthline--3: Type 2 Diabetes condition page — list three early symptoms.
GT symptoms include: increased thirst / frequent urination, persistent hunger, unintended
weight loss, fatigue, blurred vision, slow-healing sores, frequent infections, darkened skin.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, count_matches,
                        llm_text_match, Judge, parse_args)

SYMPTOMS = ["thirst", "urination", "hunger", "weight loss", "fatigue", "blurred vision",
            "slow-healing", "sores", "infection", "darkened skin"]

def main():
    a = parse_args(); j = Judge('Healthline--3', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_condition", navigated_to(t, "/condition/type-2-diabetes"),
            "expected the Type 2 Diabetes condition page")
    n = count_matches(fa, SYMPTOMS)
    j.check("answer_three_symptoms", n >= 3, f"expected >=3 listed symptoms, found {n}; final={fa!r}")
    ok, ev = llm_text_match(fa, "at least three of: increased thirst/frequent urination, persistent "
                            "hunger, unintended weight loss, fatigue, blurred vision, slow-healing sores",
                            "List three early symptoms of Type 2 Diabetes.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
