#!/usr/bin/env python3
"""Healthline--1: Nutrition > Diets — the Mediterranean eating-pattern article. GT title."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (navigated_to, claim_affirmed, navigated_re, token_affirmed, resolve_db, load_run, final_answer, navigated_any, contains_any, llm_text_match, Judge, parse_args, run)
def main():
    a = parse_args(); j = Judge('Healthline--1', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_nutrition",
            navigated_re(t, r"/section/nutrition\?sub=Diets") or navigated_to(t, "/article/mediterranean-diet"),
            "expected the Nutrition > Diets filter or the article page")
    j.check("answer_names_medi", claim_affirmed(fa, "Mediterranean Diet"),
            f"expected the Mediterranean Diet article, stated affirmatively; final={fa!r}")
    ok, ev = llm_text_match(fa, "The Mediterranean Diet: A Complete Guide and Meal Plan",
                            "Which Nutrition/Diets article covers the Mediterranean eating pattern?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.check_screenshots(t)
    _init = resolve_db(a.initial_db, a.container, "instance_seed")
    _after = resolve_db(a.after_db, a.container, "instance")
    j.check_readonly(_init, _after)
    j.emit()
if __name__ == '__main__':
    run(main, 'Healthline--1')
