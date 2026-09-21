#!/usr/bin/env python3
"""Healthline--3: Type 2 Diabetes condition page — list three early symptoms.
GT symptoms include: increased thirst / frequent urination, persistent hunger, unintended
weight loss, fatigue, blurred vision, slow-healing sores, frequent infections, darkened skin.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (resolve_db, load_run, final_answer, navigated_to, count_groups, llm_text_match, Judge, parse_args, run)

SYMPTOM_GROUPS = [["thirst", "urination"], ["hunger"], ["weight loss"], ["fatigue"],
                  ["blurred vision"], ["slow-healing", "sores"], ["infection"], ["darkened skin"]]

def main():
    a = parse_args(); j = Judge('Healthline--3', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_condition", navigated_to(t, "/condition/type-2-diabetes"),
            "expected the Type 2 Diabetes condition page")
    n = count_groups(fa, SYMPTOM_GROUPS)
    j.check("answer_three_symptoms", n >= 3, f"expected >=3 listed symptoms, found {n}; final={fa!r}")
    ok, ev = llm_text_match(fa, "at least three of: increased thirst/frequent urination, persistent "
                            "hunger, unintended weight loss, fatigue, blurred vision, slow-healing sores",
                            "List three early symptoms of Type 2 Diabetes.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.check_screenshots(t)
    _init = resolve_db(a.initial_db, a.container, "instance_seed")
    _after = resolve_db(a.after_db, a.container, "instance")
    j.check_readonly(_init, _after)
    j.emit()

if __name__ == '__main__':
    run(main, 'Healthline--3')
