#!/usr/bin/env python3
"""Healthline--1: Nutrition > Diets — the Mediterranean eating-pattern article. GT title."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_any, contains_any,
                        llm_text_match, Judge, parse_args)
def main():
    a = parse_args(); j = Judge('Healthline--1', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_nutrition", navigated_any(t, ["/section/nutrition", "/article/mediterranean-diet"]),
            "expected the Nutrition/Diets browse or the article")
    j.check("answer_names_medi", contains_any(fa, ["Mediterranean Diet"]),
            f"expected the Mediterranean Diet article; final={fa!r}")
    ok, ev = llm_text_match(fa, "The Mediterranean Diet: A Complete Guide and Meal Plan",
                            "Which Nutrition/Diets article covers the Mediterranean eating pattern?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()
if __name__ == "__main__":
    main()
