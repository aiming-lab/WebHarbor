#!/usr/bin/env python3
"""Healthline--12: open both Type 1 and Type 2 Diabetes pages; which is autoimmune?
GT: Type 1 Diabetes is the autoimmune condition. Requires opening BOTH condition pages.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (pair_affirmed, resolve_db, load_run, final_answer, navigated_to, contains_all, contains_any, llm_text_match, Judge, parse_args, run)

def main():
    a = parse_args(); j = Judge('Healthline--12', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_type1", navigated_to(t, "/condition/type-1-diabetes"), "expected the Type 1 page")
    j.check("nav_type2", navigated_to(t, "/condition/type-2-diabetes"), "expected the Type 2 page")
    j.check("answer_type1_autoimmune", pair_affirmed(fa, "type 1", "autoimmune"),
            f"expected Type 1 asserted as the autoimmune condition in one clause; final={fa!r}")
    j.check("answer_type2_not_claimed",
            not pair_affirmed(fa, "type 2", "autoimmune"),
            f"the answer must not assert Type 2 as autoimmune without negating it; final={fa!r}")
    ok, ev = llm_text_match(fa, "Type 1 Diabetes is the autoimmune condition",
                            "Which diabetes type is described as an autoimmune condition?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.check_screenshots(t)
    _init = resolve_db(a.initial_db, a.container, "instance_seed")
    _after = resolve_db(a.after_db, a.container, "instance")
    j.check_readonly(_init, _after)
    j.emit()

if __name__ == '__main__':
    run(main, 'Healthline--12')
